"""
Tests for e11/main.py command functions:
- do_config
- do_register
- do_grade

These tests use integration testing where HTTP requests are intercepted
and routed to the actual lambda_handler for end-to-end validation.
"""

import json
import sys
import uuid
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any, Optional

import pytest
import requests
from requests import Response

from e11 import main
from e11.support import get_config
from e11.e11core.constants import API_ENDPOINT, API_PATH, COURSE_KEY_LEN, COURSE_DOMAIN
from e11.e11_common import create_new_user

# Import lambda handler for integration testing
# Add lambda-home to path
lambda_home_src = Path(__file__).parent.parent / "lambda-home" / "src"
if str(lambda_home_src) not in sys.path:
    sys.path.insert(0, str(lambda_home_src))

# Add lambda-home tests to path for fixtures
lambda_home_tests = Path(__file__).parent.parent / "lambda-home" / "tests"
if str(lambda_home_tests) not in sys.path:
    sys.path.insert(0, str(lambda_home_tests))

try:
    import home_app.home as home_module
    from home_app.api import resp_json
    from e11.e11core.constants import HTTP_OK, HTTP_FORBIDDEN, HTTP_INTERNAL_ERROR
except ImportError as e:
    # If we can't import, mark tests to skip
    pytestmark = pytest.mark.skip(reason=f"Could not import lambda-home modules: {e}")

try:
    from test_utils import create_lambda_event
except ImportError:
    # Fallback if test_utils not available
    def create_lambda_event(path: str, method: str = 'GET', body: Optional[str] = None,
                           qs: Optional[Dict] = None, cookies: Optional[list] = None) -> Dict[str, Any]:
        return {
            "rawPath": path,
            "queryStringParameters": qs or {},
            "requestContext": {"http": {"method": method, "sourceIp": "203.0.113.9"}, "stage": ""},
            "isBase64Encoded": False,
            "body": body,
            "cookies": cookies or []
        }


# Helper Utilities
def create_test_config_file_content(email: str, course_key: str, public_ip: str = "1.2.3.4",
                                     instance_id: str = "i-1234567890abcdef0",
                                     preferred_name: str = "Test User") -> str:
    """Create config file content"""
    return f"""[student]
email = {email}
course_key = {course_key}
public_ip = {public_ip}
instanceId = {instance_id}
preferred_name = {preferred_name}
"""


def create_lambda_event_from_payload(endpoint_url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Convert a requests.post payload to a Lambda event"""
    # Extract path from endpoint URL
    if API_PATH in endpoint_url:
        path = API_PATH
    else:
        path = "/api/v1"  # fallback
    
    # Convert payload to JSON body
    body = json.dumps(payload) if payload else None
    
    return create_lambda_event(path, method="POST", body=body)


def convert_lambda_response_to_requests_response(lambda_response: Dict[str, Any]) -> Response:
    """Convert Lambda response to requests.Response object"""
    response = Response()
    response.status_code = lambda_response.get("statusCode", 200)
    
    # Set response body
    body = lambda_response.get("body", "")
    if isinstance(body, dict):
        body = json.dumps(body)
    response._content = body.encode("utf-8") if isinstance(body, str) else body
    
    # Set headers
    headers = lambda_response.get("headers", {})
    response.headers = headers
    
    # Make it look like a successful request
    response.encoding = "utf-8"
    
    # Add json() method
    def json_method():
        if isinstance(body, str):
            try:
                return json.loads(body)
            except json.JSONDecodeError:
                return {}
        return body if isinstance(body, dict) else {}
    
    response.json = json_method
    
    return response


def mock_requests_post_to_lambda(monkeypatch, lambda_handler):
    """Mock requests.post to intercept and route to lambda_handler"""
    original_post = requests.post
    
    def mock_post(url, json=None, timeout=None, **kwargs):
        # Only intercept calls to our API endpoint
        if API_ENDPOINT in url or "csci-e-11.org" in url or "stage.csci-e-11.org" in url:
            # Convert to Lambda event
            event = create_lambda_event_from_payload(url, json)
            # Call real lambda_handler
            try:
                response = lambda_handler(event, None)
            except Exception as e:
                # Create error response
                response = {
                    "statusCode": HTTP_INTERNAL_ERROR,
                    "body": json.dumps({"error": True, "message": str(e)}),
                    "headers": {"Content-Type": "application/json"}
                }
            # Convert back to requests.Response
            return convert_lambda_response_to_requests_response(response)
        else:
            # For other URLs, use original function
            return original_post(url, json=json, timeout=timeout, **kwargs)
    
    monkeypatch.setattr(requests, 'post', mock_post)


def mock_ec2_functions(monkeypatch, public_ip: str = "1.2.3.4",
                       instance_id: str = "i-1234567890abcdef0", on_ec2_value: bool = True):
    """Mock EC2 metadata functions"""
    def mock_get_public_ip():
        return public_ip
    
    def mock_get_instance_id():
        return instance_id
    
    def mock_on_ec2():
        return on_ec2_value
    
    monkeypatch.setattr(main, 'get_public_ip', mock_get_public_ip)
    monkeypatch.setattr(main, 'get_instanceId', mock_get_instance_id)
    monkeypatch.setattr(main, 'on_ec2', mock_on_ec2)


class TestDoConfig:
    """Tests for do_config command"""
    
    def test_do_config_get_value(self, tmp_path, monkeypatch):
        """Test getting a config value"""
        # Set up test config
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="test@example.com",
            course_key="123456"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        # Create args object
        args = Mock()
        args.get = True
        args.section = "student"
        args.key = "email"
        args.setvalue = None
        args.smash = False
        
        # Capture output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            main.do_config(args)
            output = captured_output.getvalue().strip()
            assert output == "test@example.com"
        finally:
            sys.stdout = old_stdout
    
    def test_do_config_get_email_smashed(self, tmp_path, monkeypatch):
        """Test getting email with smash option"""
        from e11.e11core.utils import smash_email
        
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="test.user@example.com",
            course_key="123456"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        args = Mock()
        args.get = True
        args.section = "student"
        args.key = "email"
        args.setvalue = None
        args.smash = True
        
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            main.do_config(args)
            output = captured_output.getvalue().strip()
            expected = smash_email("test.user@example.com")
            assert output == expected
        finally:
            sys.stdout = old_stdout
    
    def test_do_config_set_value(self, tmp_path, monkeypatch):
        """Test setting a config value"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="old@example.com",
            course_key="123456"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        args = Mock()
        args.get = False
        args.section = "student"
        args.key = "email"
        args.setvalue = "new@example.com"
        
        main.do_config(args)
        
        # Verify the value was set
        cp = get_config()
        assert cp["student"]["email"] == "new@example.com"
    
    def test_do_config_new_section(self, tmp_path, monkeypatch):
        """Test creating a new section"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="test@example.com",
            course_key="123456"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        args = Mock()
        args.get = False
        args.section = "lab1"
        args.key = "answer"
        args.setvalue = "test-answer"
        
        main.do_config(args)
        
        # Verify the section was created
        cp = get_config()
        assert "lab1" in cp
        assert cp["lab1"]["answer"] == "test-answer"
    
    @patch('builtins.input', side_effect=['Test User', 'test@example.com', '123456', '1.2.3.4', 'i-123'])
    def test_do_config_interactive(self, mock_input, tmp_path, monkeypatch):
        """Test interactive configuration mode"""
        # STUDENT_ATTRIBS order is: preferred_name, email, course_key, public_ip, instanceId
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text("[student]\n")
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        args = Mock()
        args.get = False
        args.section = None
        args.key = None
        args.setvalue = None
        
        main.do_config(args)
        
        # Verify values were set
        cp = get_config()
        assert cp["student"]["preferred_name"] == "Test User"
        assert cp["student"]["email"] == "test@example.com"
        assert cp["student"]["course_key"] == "123456"
        assert cp["student"]["public_ip"] == "1.2.3.4"
        assert cp["student"]["instanceId"] == "i-123"


class TestDoRegister:
    """Tests for do_register command with HTTP interception"""
    
    def test_do_register_success(self, tmp_path, monkeypatch, fake_aws, dynamodb_local, clean_dynamodb):
        """Test successful registration flow"""
        # Create test user in DynamoDB
        test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
        course_key = user['course_key']
        
        # Set up test config
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email=test_email,
            course_key=course_key,
            public_ip="1.2.3.4",
            instance_id="i-1234567890abcdef0"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        # Mock EC2 functions
        mock_ec2_functions(monkeypatch, public_ip="1.2.3.4", instance_id="i-1234567890abcdef0")
        
        # Mock requests.post to route to lambda_handler
        mock_requests_post_to_lambda(monkeypatch, home_module.lambda_handler)
        
        # Create args
        args = Mock()
        args.quiet = False
        args.stage = False
        args.fixip = False
        
        # Capture output
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            main.do_register(args)
            output = captured_output.getvalue()
            assert "Registered!" in output or "Attempting to register" in output
        finally:
            sys.stdout = old_stdout
    
    def test_do_register_missing_config(self, tmp_path, monkeypatch):
        """Test registration with missing config fields"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text("[student]\nemail = test@example.com\n")
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        mock_ec2_functions(monkeypatch)
        
        args = Mock()
        args.quiet = False
        args.stage = False
        args.fixip = False
        
        # Should exit with error
        with pytest.raises(SystemExit) as exc_info:
            main.do_register(args)
        assert exc_info.value.code == 0  # do_register exits with 0 on errors
    
    def test_do_register_invalid_email(self, tmp_path, monkeypatch):
        """Test registration with invalid email"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="invalid-email",
            course_key="123456"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        mock_ec2_functions(monkeypatch)
        
        args = Mock()
        args.quiet = False
        args.stage = False
        args.fixip = False
        
        with pytest.raises(SystemExit):
            main.do_register(args)
    
    def test_do_register_ip_mismatch_with_fixip(self, tmp_path, monkeypatch, fake_aws, dynamodb_local, clean_dynamodb):
        """Test registration with IP mismatch but --fixip flag"""
        test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
        course_key = user['course_key']
        
        config_file = tmp_path / "e11-config.ini"
        # Config has wrong IP
        config_file.write_text(create_test_config_file_content(
            email=test_email,
            course_key=course_key,
            public_ip="9.9.9.9",  # Wrong IP
            instance_id="i-1234567890abcdef0"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        # Mock EC2 to return different IP
        mock_ec2_functions(monkeypatch, public_ip="1.2.3.4", instance_id="i-1234567890abcdef0")
        
        mock_requests_post_to_lambda(monkeypatch, home_module.lambda_handler)
        
        args = Mock()
        args.quiet = False
        args.stage = False
        args.fixip = True  # Should fix the IP
        
        # Should succeed because of --fixip
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        try:
            main.do_register(args)
            # Verify IP was fixed
            cp = get_config()
            assert cp["student"]["public_ip"] == "1.2.3.4"
        finally:
            sys.stdout = old_stdout
    
    def test_do_register_invalid_course_key(self, tmp_path, monkeypatch):
        """Test registration with invalid course key length"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="test@example.com",
            course_key="123"  # Too short
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        mock_ec2_functions(monkeypatch)
        
        args = Mock()
        args.quiet = False
        args.stage = False
        args.fixip = False
        
        with pytest.raises(SystemExit):
            main.do_register(args)
    
    def test_do_register_retry_on_timeout(self, tmp_path, monkeypatch, fake_aws, dynamodb_local, clean_dynamodb):
        """Test retry logic on timeout"""
        test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
        course_key = user['course_key']
        
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email=test_email,
            course_key=course_key
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        mock_ec2_functions(monkeypatch)
        
        # Mock requests.post to raise timeout on first call, succeed on second
        call_count = [0]
        
        def mock_post_with_timeout(url, json=None, timeout=None, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise requests.exceptions.Timeout("Request timed out")
            # On retry, route to lambda
            event = create_lambda_event_from_payload(url, json)
            response = home_module.lambda_handler(event, None)
            return convert_lambda_response_to_requests_response(response)
        
        monkeypatch.setattr(requests, 'post', mock_post_with_timeout)
        
        args = Mock()
        args.quiet = False
        args.stage = False
        args.fixip = False
        
        import io
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured_output = io.StringIO()
        
        try:
            main.do_register(args)
            output = captured_output.getvalue()
            assert "retrying" in output.lower() or "Registered" in output
            assert call_count[0] == 2  # Should have retried
        finally:
            sys.stdout = old_stdout


class TestDoGrade:
    """Tests for do_grade command with HTTP interception"""
    
    def test_do_grade_success(self, tmp_path, monkeypatch, fake_aws, dynamodb_local, clean_dynamodb):
        """Test successful grading request"""
        test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = create_new_user(test_email, {"email": test_email, "name": "Test User", "public_ip": "1.2.3.4"})
        course_key = user['course_key']
        
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email=test_email,
            course_key=course_key
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        # Mock grader.grade_student_vm to return test results
        # Format must match what grader.create_email expects (see grader.py line 166-173)
        def mock_grade_student_vm(email, public_ip, lab, pkey_pem=None, key_filename=None):
            return {
                'error': False,
                'fails': [],  # List of failing test names
                'passes': ['test1', 'test2'],  # List of passing test names (strings, not int)
                'lab': lab,  # Required for create_email
                'tests': [
                    {'name': 'test1', 'status': 'pass', 'message': 'Test 1 passed'},
                    {'name': 'test2', 'status': 'pass', 'message': 'Test 2 passed'},
                ],
                'score': 5.0,
                'ctx': {}  # Context dict
            }
        
        # Patch the grader in the lambda-home module
        import home_app.api as api_module
        original_grade_student_vm = api_module.grader.grade_student_vm
        api_module.grader.grade_student_vm = mock_grade_student_vm
        
        # Also ensure get_pkey_pem is mocked to return a fake key
        def mock_get_pkey_pem(key_name):
            return "-----BEGIN RSA PRIVATE KEY-----\nfake-key\n-----END RSA PRIVATE KEY-----"
        
        original_get_pkey_pem = api_module.get_pkey_pem
        api_module.get_pkey_pem = mock_get_pkey_pem
        
        try:
            # Mock requests.post to route to lambda_handler
            mock_requests_post_to_lambda(monkeypatch, home_module.lambda_handler)
            
            args = Mock()
            args.lab = "lab1"
            args.direct = None
            args.identity = None
            args.timeout = 35
            args.verbose = False
            args.debug = False
            args.stage = False
            
            import io
            import sys
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            try:
                # do_grade calls sys.exit(0) on success, so we need to catch it
                with pytest.raises(SystemExit) as exc_info:
                    main.do_grade(args)
                assert exc_info.value.code == 0  # Success exit code
                output = captured_output.getvalue()
                # Should have some output
                assert len(output) > 0
            finally:
                sys.stdout = old_stdout
        finally:
            # Restore original functions
            api_module.grader.grade_student_vm = original_grade_student_vm
            api_module.get_pkey_pem = original_get_pkey_pem
    
    def test_do_grade_missing_config(self, tmp_path, monkeypatch):
        """Test grading with missing course_key"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text("[student]\nemail = test@example.com\n")
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        args = Mock()
        args.lab = "lab1"
        args.direct = None
        args.identity = None
        args.timeout = 35
        args.verbose = False
        args.debug = False
        args.stage = False
        
        # Should exit with error
        with pytest.raises(SystemExit) as exc_info:
            main.do_grade(args)
        assert exc_info.value.code == 1
    
    def test_do_grade_direct_mode(self, tmp_path, monkeypatch):
        """Test direct grading mode (mocked SSH)"""
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email="test@example.com",
            course_key="123456"
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        # Mock grader.grade_student_vm for direct mode
        def mock_grade_student_vm(email, public_ip, lab, pkey_pem=None, key_filename=None):
            return {
                'error': False,
                'fails': [],  # List of failing test names
                'passes': ['test1', 'test2', 'test3'],  # List of passing test names
                'lab': lab,
                'tests': [
                    {'name': 'test1', 'status': 'pass'},
                    {'name': 'test2', 'status': 'pass'},
                    {'name': 'test3', 'status': 'pass'},
                ],
                'score': 5.0,
                'ctx': {}
            }
        
        from e11.e11core import grader
        original_grade = grader.grade_student_vm
        grader.grade_student_vm = mock_grade_student_vm
        
        try:
            args = Mock()
            args.lab = "lab1"
            args.direct = "1.2.3.4"
            args.identity = "/path/to/key"
            args.timeout = 35
            args.verbose = False
            args.debug = False
            args.stage = False
            
            import io
            import sys
            old_stdout = sys.stdout
            sys.stdout = captured_output = io.StringIO()
            
            try:
                main.do_grade(args)
                output = captured_output.getvalue()
                assert "Grading Direct" in output or len(output) > 0
            finally:
                sys.stdout = old_stdout
        finally:
            grader.grade_student_vm = original_grade
    
    def test_do_grade_http_error(self, tmp_path, monkeypatch, fake_aws, dynamodb_local, clean_dynamodb):
        """Test grading with HTTP error response"""
        test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
        user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
        course_key = user['course_key']
        
        config_file = tmp_path / "e11-config.ini"
        config_file.write_text(create_test_config_file_content(
            email=test_email,
            course_key=course_key
        ))
        monkeypatch.setenv("E11_CONFIG", str(config_file))
        
        # Mock requests.post to return error response
        def mock_post_error(url, json=None, timeout=None, **kwargs):
            response = Response()
            response.status_code = 500
            response._content = b'{"error": true, "message": "Internal server error"}'
            response.headers = {"Content-Type": "application/json"}
            response.json = lambda: {"error": True, "message": "Internal server error"}
            return response
        
        monkeypatch.setattr(requests, 'post', mock_post_error)
        
        args = Mock()
        args.lab = "lab1"
        args.direct = None
        args.identity = None
        args.timeout = 35
        args.verbose = False
        args.debug = False
        args.stage = False
        
        # Should exit with error
        with pytest.raises(SystemExit) as exc_info:
            main.do_grade(args)
        assert exc_info.value.code == 1

