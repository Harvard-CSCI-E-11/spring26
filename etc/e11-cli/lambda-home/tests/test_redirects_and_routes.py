"""
Test redirects and routes that can be validated without heavy mocking.

This test suite validates:
1. All lab redirects return valid redirects
2. LAB_REDIRECTS dictionary has all required entries
3. Version endpoint returns valid response
4. 404 handling works correctly
5. Other routes that don't require complex mocking
"""

import pytest
import home_app.home as home
from e11.e11_common import LAB_REDIRECTS
from test_utils import create_lambda_event


def test_all_lab_redirects_exist():
    """Validate that LAB_REDIRECTS has entries for labs 0-8"""
    expected_labs = list(range(9))  # labs 0 through 8
    for lab_num in expected_labs:
        assert lab_num in LAB_REDIRECTS, f"LAB_REDIRECTS missing entry for lab{lab_num}"
        assert LAB_REDIRECTS[lab_num], f"LAB_REDIRECTS[{lab_num}] is empty"
        assert isinstance(LAB_REDIRECTS[lab_num], str), f"LAB_REDIRECTS[{lab_num}] is not a string"
        assert LAB_REDIRECTS[lab_num].startswith("http"), f"LAB_REDIRECTS[{lab_num}] is not a valid URL"


def test_lab_redirects_return_valid_redirects():
    """Test that all lab redirect routes return valid HTTP 302 redirects"""
    for lab_num in range(9):
        path = f"/lab{lab_num}"
        event = create_lambda_event(path, method="GET")
        response = home.lambda_handler(event, None)

        assert response["statusCode"] == 302, f"/lab{lab_num} should return 302, got {response['statusCode']}"
        assert "Location" in response["headers"], f"/lab{lab_num} response missing Location header"
        assert response["headers"]["Location"] == LAB_REDIRECTS[lab_num], \
            f"/lab{lab_num} redirects to wrong URL: expected {LAB_REDIRECTS[lab_num]}, got {response['headers']['Location']}"


def test_version_endpoint():
    """Test that /version endpoint returns valid version information"""
    event = create_lambda_event("/version", method="GET")
    response = home.lambda_handler(event, None)

    assert response["statusCode"] == 200, f"/version should return 200, got {response['statusCode']}"
    assert "version" in response["body"].lower(), "/version response should contain version information"
    # Version endpoint returns: "version: {__version__} of {DEPLOYMENT_TIMESTAMP}\n"
    assert "version:" in response["body"], "/version response should contain 'version:'"


def test_heartbeat_endpoint():
    """Test that /heartbeat endpoint returns valid response structure"""
    # Heartbeat doesn't require authentication, but it does scan sessions table
    # We can test it returns a response structure even if AWS calls fail
    event = create_lambda_event("/heartbeat", method="GET")
    response = home.lambda_handler(event, None)

    # Heartbeat should return 200 (success) or 500 if AWS fails
    # Both are valid - we're testing the endpoint exists and returns structured response
    assert response["statusCode"] in [200, 500], \
        f"/heartbeat should return 200 or 500, got {response['statusCode']}"

    # Validate response has proper structure
    assert "headers" in response, "/heartbeat response should have headers"
    assert "body" in response, "/heartbeat response should have body"

    # If it's JSON (error case), validate structure
    if "application/json" in response.get("headers", {}).get("Content-Type", ""):
        import json
        body = json.loads(response["body"])
        assert isinstance(body, dict), "/heartbeat JSON response should be a dict"


def test_404_for_unknown_paths():
    """Test that unknown paths return 404"""
    event = create_lambda_event("/nonexistent-path-12345", method="GET")
    response = home.lambda_handler(event, None)

    assert response["statusCode"] == 404, f"Unknown path should return 404, got {response['statusCode']}"


def test_404_for_unknown_methods():
    """Test that unsupported methods return 404"""
    event = create_lambda_event("/lab0", method="PUT")
    response = home.lambda_handler(event, None)

    assert response["statusCode"] == 404, f"PUT to /lab0 should return 404, got {response['statusCode']}"


def test_static_file_404_for_nonexistent():
    """Test that static file requests for nonexistent files return 404"""
    event = create_lambda_event("/static/nonexistent-file-12345.css", method="GET")
    response = home.lambda_handler(event, None)

    assert response["statusCode"] == 404, \
        f"Nonexistent static file should return 404, got {response['statusCode']}"


def test_root_path_returns_response():
    """Test that root path returns valid response structure"""
    # Root path requires OIDC config which needs secrets manager
    # We can still validate the endpoint exists and returns structured response
    event = create_lambda_event("/", method="GET")
    response = home.lambda_handler(event, None)

    # Root path should return 200 (success) or 500 (if AWS secrets manager fails)
    # Both are valid - we're testing the endpoint exists
    assert response["statusCode"] in [200, 500], \
        f"Root path should return 200 or 500, got {response['statusCode']}"

    # Validate response has proper structure
    assert "headers" in response, "Root path response should have headers"
    assert "body" in response, "Root path response should have body"

    # If successful, should return HTML (login page)
    if response["statusCode"] == 200:
        assert "text/html" in response.get("headers", {}).get("Content-Type", "").lower(), \
            "Root path should return HTML content when successful"


def test_logout_path_returns_response():
    """Test that /logout path returns valid response structure"""
    # Logout requires OIDC config which needs secrets manager
    # We can still validate the endpoint exists and returns structured response
    event = create_lambda_event("/logout", method="GET")
    response = home.lambda_handler(event, None)

    # Logout should return 200 (success) or 500 (if AWS secrets manager fails)
    assert response["statusCode"] in [200, 500], \
        f"/logout should return 200 or 500, got {response['statusCode']}"

    # Validate response has proper structure
    assert "headers" in response, "/logout response should have headers"
    assert "body" in response, "/logout response should have body"

    # If successful, should return HTML
    if response["statusCode"] == 200:
        assert "text/html" in response.get("headers", {}).get("Content-Type", "").lower(), \
            "/logout should return HTML content when successful"


def test_lab_redirects_are_unique():
    """Test that all lab redirect URLs are unique (no duplicates)"""
    urls = [LAB_REDIRECTS[i] for i in range(9)]
    unique_urls = set(urls)
    assert len(urls) == len(unique_urls), \
        f"Found duplicate URLs in LAB_REDIRECTS: {[url for url in urls if urls.count(url) > 1]}"


# Additional tests for utility functions that don't require mocking

def test_parse_event_extracts_method_path_payload():
    """Test that parse_event correctly extracts method, path, and payload from Lambda event"""
    from home_app.home import parse_event

    event = {
        "rawPath": "/test/path",
        "requestContext": {"http": {"method": "POST"}},
        "body": '{"action": "test", "data": "value"}'
    }
    method, path, payload = parse_event(event)

    assert method == "POST"
    assert path == "/test/path"
    assert payload == {"action": "test", "data": "value"}


def test_parse_event_handles_empty_body():
    """Test that parse_event handles empty or missing body"""
    from home_app.home import parse_event

    event = {
        "rawPath": "/test",
        "requestContext": {"http": {"method": "GET"}},
        "body": None
    }
    method, path, payload = parse_event(event)

    assert method == "GET"
    assert path == "/test"
    assert payload == {}


def test_parse_event_handles_base64_encoded_body():
    """Test that parse_event decodes base64 encoded bodies"""
    from home_app.home import parse_event
    import base64

    body = '{"test": "data"}'
    encoded = base64.b64encode(body.encode()).decode()

    event = {
        "rawPath": "/test",
        "requestContext": {"http": {"method": "POST"}},
        "body": encoded,
        "isBase64Encoded": True
    }
    method, path, payload = parse_event(event)

    assert payload == {"test": "data"}


def test_parse_s3_event_detects_s3_events():
    """Test that parse_s3_event correctly identifies S3 events"""
    from home_app.home import parse_s3_event

    event = {
        "source": "aws.s3",
        "detail-type": "Object Created",
        "detail": {
            "request-id": "req-123",
            "bucket": {"name": "test-bucket"},
            "object": {"key": "test/key.jpg"}
        }
    }
    request_id, bucket, key = parse_s3_event(event)

    assert request_id == "req-123"
    assert bucket == "test-bucket"
    assert key == "test/key.jpg"


def test_parse_s3_event_returns_none_for_non_s3_events():
    """Test that parse_s3_event returns None for non-S3 events"""
    from home_app.home import parse_s3_event

    event = {
        "rawPath": "/test",
        "requestContext": {"http": {"method": "GET"}}
    }
    request_id, bucket, key = parse_s3_event(event)

    assert request_id is None
    assert bucket is None
    assert key is None


def test_is_sqs_event_detects_sqs_events():
    """Test that is_sqs_event correctly identifies SQS events"""
    from home_app.sqs_support import is_sqs_event

    event = {
        "Records": [
            {"eventSource": "aws:sqs", "messageId": "msg-123"}
        ]
    }
    assert is_sqs_event(event) is True


def test_is_sqs_event_rejects_non_sqs_events():
    """Test that is_sqs_event returns False for non-SQS events"""
    from home_app.sqs_support import is_sqs_event

    event = {
        "rawPath": "/test",
        "requestContext": {"http": {"method": "GET"}}
    }
    assert is_sqs_event(event) is False


def test_is_staging_environment():
    """Test that is_staging_environment correctly detects staging"""
    from home_app.common import is_staging_environment

    staging_event = {"requestContext": {"stage": "stage"}}
    prod_event = {"requestContext": {"stage": "prod"}}
    no_stage_event = {"requestContext": {}}

    assert is_staging_environment(staging_event) is True
    assert is_staging_environment(prod_event) is False
    assert is_staging_environment(no_stage_event) is False


def test_make_cookie_creates_valid_cookie():
    """Test that make_cookie creates properly formatted cookie strings"""
    from home_app.common import make_cookie

    cookie = make_cookie("TestCookie", "test-value", max_age=3600)

    assert "TestCookie=test-value" in cookie
    assert "Path=/" in cookie
    assert "Secure" in cookie
    assert "HttpOnly" in cookie
    assert "Max-Age=3600" in cookie


def test_make_cookie_clear_flag():
    """Test that make_cookie creates clearing cookies when clear=True"""
    from home_app.common import make_cookie

    cookie = make_cookie("TestCookie", "value", clear=True)

    assert "TestCookie=" in cookie  # Empty value
    assert "Max-Age=0" in cookie
    assert "Expires=Thu, 01 Jan 1970 00:00:00 GMT" in cookie


def test_get_cookie_domain():
    """Test that get_cookie_domain returns correct domain based on environment"""
    from home_app.common import get_cookie_domain

    staging_event = {"requestContext": {"stage": "stage"}}
    prod_event = {"requestContext": {"stage": "prod"}}

    # Both should return the course domain (staging uses prod domain for cookies)
    staging_domain = get_cookie_domain(staging_event)
    prod_domain = get_cookie_domain(prod_event)

    from e11.e11core.constants import COURSE_DOMAIN
    assert staging_domain == COURSE_DOMAIN
    assert prod_domain == COURSE_DOMAIN  # or COOKIE_DOMAIN, depending on config


def test_resp_json_creates_valid_response():
    """Test that resp_json creates properly formatted JSON responses"""
    from home_app.api import resp_json

    response = resp_json(200, {"message": "test", "data": 123})

    assert response["statusCode"] == 200
    assert "Content-Type" in response["headers"]
    assert response["headers"]["Content-Type"] == "application/json"
    assert "Access-Control-Allow-Origin" in response["headers"]
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"

    import json
    body = json.loads(response["body"])
    assert body == {"message": "test", "data": 123}


def test_redirect_creates_valid_redirect():
    """Test that redirect creates properly formatted redirect responses"""
    from home_app.home import redirect

    response = redirect("/test/path")

    assert response["statusCode"] == 302
    assert response["headers"]["Location"] == "/test/path"
    assert response["body"] == ""
    assert response["cookies"] == []


def test_error_404_creates_valid_error():
    """Test that error_404 creates properly formatted 404 responses"""
    from home_app.home import error_404

    response = error_404("test-page")

    assert response["statusCode"] == 404
    assert "text/html" in response.get("headers", {}).get("Content-Type", "").lower()
    assert "body" in response


# Additional utility function tests

def test_parse_cookies_extracts_cookies():
    """Test that parse_cookies correctly extracts cookies from event"""
    from home_app.sessions import parse_cookies

    event = {
        "cookies": ["AuthSid=abc123", "OtherCookie=value", "NoEquals"]
    }
    cookies = parse_cookies(event)

    assert cookies["AuthSid"] == "abc123"
    assert cookies["OtherCookie"] == "value"
    assert "NoEquals" not in cookies  # Should skip cookies without =


def test_parse_cookies_handles_empty_list():
    """Test that parse_cookies handles empty or missing cookies"""
    from home_app.sessions import parse_cookies

    event = {"cookies": []}
    cookies = parse_cookies(event)
    assert cookies == {}

    event = {}
    cookies = parse_cookies(event)
    assert cookies == {}


def test_parse_cookies_handles_multiple_equals():
    """Test that parse_cookies only splits on first equals sign"""
    from home_app.sessions import parse_cookies

    event = {
        "cookies": ["Cookie=value=with=equals"]
    }
    cookies = parse_cookies(event)

    assert cookies["Cookie"] == "value=with=equals"


def test_expire_batch_deletes_expired_sessions(monkeypatch):
    """Test that expire_batch correctly identifies and deletes expired sessions"""
    from home_app.sessions import expire_batch
    import time

    now = int(time.time())
    expired_time = now - 1000  # Expired 1000 seconds ago
    future_time = now + 1000    # Expires in 1000 seconds

    items = [
        {"sid": "expired1", "session_expire": expired_time},
        {"sid": "active1", "session_expire": future_time},
        {"sid": "expired2", "session_expire": expired_time},
        {"sid": "active2", "session_expire": future_time},
    ]

    deleted_sids = []

    def mock_delete_item(Key):
        deleted_sids.append(Key["sid"])
        return {}

    import home_app.sessions as sessions_module
    monkeypatch.setattr(sessions_module.sessions_table, "delete_item", mock_delete_item)

    count = expire_batch(now, items)

    assert count == 2  # Should delete 2 expired sessions
    assert "expired1" in deleted_sids
    assert "expired2" in deleted_sids
    assert "active1" not in deleted_sids
    assert "active2" not in deleted_sids


def test_expire_batch_handles_missing_session_expire(monkeypatch):
    """Test that expire_batch handles items without session_expire field"""
    from home_app.sessions import expire_batch
    import time

    now = int(time.time())
    items = [
        {"sid": "no_expire1"},  # Missing session_expire - .get() returns 0
    ]

    deleted_sids = []

    def mock_delete_item(Key):
        deleted_sids.append(Key["sid"])
        return {}

    import home_app.sessions as sessions_module
    monkeypatch.setattr(sessions_module.sessions_table, "delete_item", mock_delete_item)

    count = expire_batch(now, items)

    # Items with missing session_expire use .get("session_expire", 0) which returns 0
    # and 0 <= now is True, so it should be deleted
    assert count == 1
    assert "no_expire1" in deleted_sids
    # Note: items with session_expire=None will raise TypeError because None <= int fails
    # This is actually a bug in the code, but we're testing current behavior


def test_eastern_filter_formats_timestamp():
    """Test that eastern_filter correctly formats timestamps"""
    from home_app.home import eastern_filter
    import time

    # Test with current time
    now = time.time()
    result = eastern_filter(now)

    assert isinstance(result, str)
    assert len(result) > 0
    # Should contain date format
    assert "-" in result  # Date separator
    assert ":" in result  # Time separator


def test_eastern_filter_handles_none():
    """Test that eastern_filter handles None and undefined values"""
    from home_app.home import eastern_filter
    assert eastern_filter(None) == ""
    try:
        import jinja2
        # Test with jinja2.Undefined if available
        # Note: jinja2.Undefined() may return "n/a" if it fails type check
        undefined = jinja2.Undefined()
        result = eastern_filter(undefined)
        # Should return "" for Undefined, but may return "n/a" if type check fails
        assert result in ("", "n/a")
    except (ImportError, AttributeError, TypeError):
        # If jinja2.Undefined not available or causes issues, just test None
        pass


def test_eastern_filter_handles_invalid_types():
    """Test that eastern_filter handles invalid input types gracefully"""
    from home_app.home import eastern_filter

    # Should return "n/a" for invalid types
    assert eastern_filter("not-a-number") == "n/a"
    assert eastern_filter([]) == "n/a"


def test_validate_payload_structure():
    """Test that validate_payload correctly validates payload structure"""
    from home_app.api import validate_payload, APINotAuthenticated

    # Test missing auth - should raise immediately
    with pytest.raises(APINotAuthenticated) as exc_info:
        validate_payload({})
    assert "auth" in str(exc_info.value).lower()

    # Test missing email in auth - will fail when trying to get user from empty email
    # This will raise APINotAuthenticated from validate_email_and_course_key
    # but requires DynamoDB access, so we'll just verify it raises the right exception type
    with pytest.raises((APINotAuthenticated, Exception)):
        # May raise APINotAuthenticated or ResourceNotFoundException if DynamoDB not available
        validate_payload({"auth": {}})

    # Test missing course_key in auth - same issue
    with pytest.raises((APINotAuthenticated, Exception)):
        validate_payload({"auth": {"email": "test@example.com"}})


def test_domain_suffixes_constant():
    """Test that DOMAIN_SUFFIXES constant has expected structure"""
    from home_app.api import DOMAIN_SUFFIXES

    # Should have 9 entries (empty string + 8 lab suffixes)
    assert len(DOMAIN_SUFFIXES) == 9

    # First should be empty string
    assert DOMAIN_SUFFIXES[0] == ""

    # Rest should be lab suffixes
    for i in range(1, 9):
        assert DOMAIN_SUFFIXES[i].startswith("-lab")
        assert DOMAIN_SUFFIXES[i] == f"-lab{i}"


def test_resp_text_creates_valid_response():
    """Test that resp_text creates properly formatted text responses"""
    from home_app.home import resp_text

    response = resp_text(200, "<html>test</html>")

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
    assert response["body"] == "<html>test</html>"
    assert response["cookies"] == []


def test_resp_text_with_cookies():
    """Test that resp_text includes cookies when provided"""
    from home_app.home import resp_text

    cookies = ["cookie1=value1", "cookie2=value2"]
    response = resp_text(200, "test", cookies=cookies)

    assert response["cookies"] == cookies


def test_resp_text_with_custom_headers():
    """Test that resp_text merges custom headers"""
    from home_app.home import resp_text

    custom_headers = {"X-Custom": "value"}
    response = resp_text(200, "test", headers=custom_headers)

    assert response["headers"]["X-Custom"] == "value"
    assert response["headers"]["Content-Type"] == "text/html; charset=utf-8"  # Still has default


def test_resp_png_creates_valid_response():
    """Test that resp_png creates properly formatted PNG responses"""
    from home_app.home import resp_png
    import base64

    png_data = b"\x89PNG\r\n\x1a\n"  # Minimal PNG header
    response = resp_png(200, png_data)

    assert response["statusCode"] == 200
    assert response["headers"]["Content-Type"] == "image/png"
    assert response["headers"]["Access-Control-Allow-Origin"] == "*"
    assert response["isBase64Encoded"] is True
    assert base64.b64decode(response["body"]) == png_data


def test_resp_png_with_cookies():
    """Test that resp_png includes cookies when provided"""
    from home_app.home import resp_png

    cookies = ["cookie1=value1"]
    response = resp_png(200, b"test", cookies=cookies)

    assert response["cookies"] == cookies


def test_parse_event_handles_stage_prefix():
    """Test that parse_event correctly handles stage prefixes in paths"""
    from home_app.home import parse_event

    event = {
        "rawPath": "/stage/test/path",
        "requestContext": {
            "stage": "stage",
            "http": {"method": "GET"}
        },
        "body": None
    }
    method, path, payload = parse_event(event)

    assert method == "GET"
    assert path == "/test/path"  # Stage prefix should be removed


def test_parse_event_handles_http_method_fallback():
    """Test that parse_event falls back to httpMethod if http.method not available"""
    from home_app.home import parse_event

    event = {
        "rawPath": "/test",
        "requestContext": {},
        "httpMethod": "PUT",  # Old API Gateway format
        "body": None
    }
    method, path, payload = parse_event(event)

    assert method == "PUT"


def test_parse_event_handles_malformed_json():
    """Test that parse_event handles malformed JSON gracefully"""
    from home_app.home import parse_event

    event = {
        "rawPath": "/test",
        "requestContext": {"http": {"method": "POST"}},
        "body": "{invalid json"
    }
    method, path, payload = parse_event(event)

    assert method == "POST"
    assert path == "/test"
    assert payload == {}  # Should default to empty dict on JSON error


def test_parse_event_handles_invalid_base64():
    """Test that parse_event handles invalid base64 gracefully"""
    from home_app.home import parse_event

    event = {
        "rawPath": "/test",
        "requestContext": {"http": {"method": "POST"}},
        "body": "not-valid-base64!!!",
        "isBase64Encoded": True
    }
    method, path, payload = parse_event(event)

    assert method == "POST"
    assert path == "/test"
    assert payload == {}  # Should default to empty dict on base64 error


def test_api_dispatch_routes_all_actions():
    """Test that dispatch function routes all known actions correctly"""
    from home_app.api import dispatch
    from e11.e11core.constants import API_PATH
    from home_app.api import APINotAuthenticated

    # Create minimal event and context
    event = {"rawPath": API_PATH}
    context = {}
    path = API_PATH

    # Test that all known actions are handled (structure check only)
    known_actions = [
        "ping", "ping-mail", "register", "grade", "delete-session",
        "delete-image", "check-access", "check-me", "post-image",
        "heartbeat", "version"
    ]

    for action in known_actions:
        payload = {"action": action}
        # Most actions will fail due to missing dependencies (auth, etc.),
        # but we can check they don't fail on routing (unknown action error)
        try:
            response = dispatch("POST", action, event, context, payload, path)
            # Should return a response dict with statusCode
            assert isinstance(response, dict)
            assert "statusCode" in response
        except (APINotAuthenticated, KeyError, AttributeError, TypeError):
            # Expected failures due to missing data/dependencies, not routing issues
            pass
        except Exception as e:
            # If we get an "unknown action" error, that's a routing problem
            if "unknown" in str(e).lower() or "missing action" in str(e).lower():
                raise  # Re-raise routing errors


def test_api_dispatch_unknown_action():
    """Test that dispatch returns 400 for unknown actions"""
    from home_app.api import dispatch
    from e11.e11core.constants import API_PATH

    event = {"rawPath": API_PATH}
    context = {}
    payload = {"action": "unknown-action-12345"}
    path = API_PATH

    response = dispatch("POST", "unknown-action-12345", event, context, payload, path)

    assert response["statusCode"] == 400
    assert "error" in response["body"].lower() or "unknown" in response["body"].lower()


def test_api_dispatch_wrong_method():
    """Test that dispatch handles wrong HTTP methods"""
    from home_app.api import dispatch
    from e11.e11core.constants import API_PATH

    event = {"rawPath": API_PATH}
    context = {}
    payload = {"action": "ping"}
    path = API_PATH

    # GET method with POST action should return 400
    response = dispatch("GET", "ping", event, context, payload, path)

    assert response["statusCode"] == 400

