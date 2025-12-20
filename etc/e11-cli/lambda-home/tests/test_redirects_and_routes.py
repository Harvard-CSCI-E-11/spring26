"""
Test redirects and routes that can be validated without heavy mocking.

This test suite validates:
1. All lab redirects return valid redirects
2. LAB_REDIRECTS dictionary has all required entries
3. Version endpoint returns valid response
4. 404 handling works correctly
5. Other routes that don't require complex mocking
"""

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

