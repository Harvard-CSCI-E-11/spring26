"""
Tests for direct login functionality (for users created via register-email).
"""
import base64
import pytest
import uuid

from e11.e11_common import create_new_user, A, get_user_from_user_id
from e11.e11core.constants import HTTP_BAD_REQUEST, HTTP_FORBIDDEN, HTTP_FOUND, HTTP_OK
from home_app.home import lambda_handler
from test_utils import create_lambda_event


@pytest.fixture
def direct_login_user(fake_aws, dynamodb_local):
    """Create a test user WITHOUT claims for direct login testing (simulates staff account creation via register-email)"""
    test_email = f"direct-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email)  # No claims - simulates staff account creation (register-email)
    return {
        "email": test_email,
        "course_key": user[A.COURSE_KEY],
        "user_id": user[A.USER_ID]
    }


def test_direct_login_success(fake_aws, dynamodb_local, direct_login_user):
    """Test successful direct login for user without claims"""
    # Generate token
    token_data = f"{direct_login_user['user_id']}:{direct_login_user['course_key']}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    # Create event
    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    # Call handler
    response = lambda_handler(event, None)

    # Verify redirect to dashboard
    assert response["statusCode"] == HTTP_FOUND
    assert response["headers"]["Location"] == "/dashboard"

    # Verify cookie is set
    cookies = response.get("cookies", [])
    assert any("AuthSid=" in c for c in cookies)

    # Verify session exists in DynamoDB Local
    from home_app.sessions import all_sessions_for_email
    sessions = all_sessions_for_email(direct_login_user["email"])
    assert len(sessions) == 1
    assert sessions[0]["email"] == direct_login_user["email"]
    # Session will have minimal claims with email
    assert sessions[0].get("claims") is not None
    assert sessions[0]["claims"].get("email") == direct_login_user["email"]


def test_direct_login_missing_token(fake_aws, dynamodb_local):
    """Test direct login with missing token"""
    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={}
    )

    response = lambda_handler(event, None)
    assert response["statusCode"] == HTTP_BAD_REQUEST
    assert "Missing token" in response["body"]


def test_direct_login_invalid_token_format(fake_aws, dynamodb_local):
    """Test direct login with invalid base64 token"""
    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": "not-valid-base64!!!"}
    )

    response = lambda_handler(event, None)
    assert response["statusCode"] == HTTP_BAD_REQUEST
    assert "Invalid token format" in response["body"]


def test_direct_login_invalid_user_id(fake_aws, dynamodb_local):
    """Test direct login with non-existent user_id"""
    fake_user_id = str(uuid.uuid4())
    fake_course_key = "ABC123"
    token_data = f"{fake_user_id}:{fake_course_key}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    response = lambda_handler(event, None)
    assert response["statusCode"] == HTTP_FORBIDDEN
    assert "Course key mismatch" in response["body"]
    assert "email is not registered" in response["body"]


def test_direct_login_invalid_course_key(fake_aws, dynamodb_local, direct_login_user):
    """Test direct login with wrong course_key"""
    # Generate token with wrong course_key
    token_data = f"{direct_login_user['user_id']}:WRONG_KEY"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    response = lambda_handler(event, None)
    assert response["statusCode"] == HTTP_FORBIDDEN
    assert "Course key mismatch" in response["body"]
    assert direct_login_user["email"] in response["body"]


def test_direct_login_user_has_claims(fake_aws, dynamodb_local):
    """Test that users with OIDC claims are redirected to /login"""
    # Create user WITH claims (simulates OIDC user)
    test_email = f"oidc-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email, {
        "email": test_email,
        "name": "OIDC User"
    })  # Has claims

    # Generate valid token
    token_data = f"{user[A.USER_ID]}:{user[A.COURSE_KEY]}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    response = lambda_handler(event, None)
    # Should redirect to /login
    assert response["statusCode"] == HTTP_FOUND
    assert response["headers"]["Location"] == "/login"


def test_direct_login_session_created_in_db(fake_aws, dynamodb_local, direct_login_user):
    """Verify session is created in DynamoDB Local"""
    # Generate token
    token_data = f"{direct_login_user['user_id']}:{direct_login_user['course_key']}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    # Call handler
    response = lambda_handler(event, None)
    assert response["statusCode"] == HTTP_FOUND

    # Query sessions table directly
    from home_app.sessions import all_sessions_for_email
    sessions = all_sessions_for_email(direct_login_user["email"])
    assert len(sessions) == 1

    session = sessions[0]
    assert session["email"] == direct_login_user["email"]
    assert session.get("claims") is not None
    assert session["claims"].get("email") == direct_login_user["email"]


def test_direct_login_can_access_dashboard(fake_aws, dynamodb_local, direct_login_user):
    """Test end-to-end: direct login → dashboard access"""
    # Generate token
    token_data = f"{direct_login_user['user_id']}:{direct_login_user['course_key']}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    # Login
    login_event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    login_response = lambda_handler(login_event, None)
    assert login_response["statusCode"] == HTTP_FOUND

    # Extract cookie - need to extract just name=value part (before first semicolon)
    # make_cookie returns full Set-Cookie header, but parse_cookies expects just "AuthSid=value"
    cookies = login_response.get("cookies", [])
    assert len(cookies) > 0
    cookie_string = cookies[0]
    # Extract just the name=value part (before the first semicolon)
    cookie_name_value = cookie_string.split(';')[0]

    # Access dashboard with cookie
    dashboard_event = create_lambda_event(
        "/dashboard",
        method="GET",
        cookies=[cookie_name_value]
    )

    dashboard_response = lambda_handler(dashboard_event, None)
    assert dashboard_response["statusCode"] == HTTP_OK
    assert "Dashboard" in dashboard_response["body"]


def test_generate_direct_login_url():
    """Test URL generation function"""
    from e11.e11_common import generate_direct_login_url

    user_id = "test-user-id-123"
    course_key = "ABC123"

    url = generate_direct_login_url(user_id, course_key)

    assert url.startswith("https://csci-e-11.org/login-direct?token=")

    # Extract and verify token
    token = url.split("token=")[1]
    # Decode token
    padding = len(token) % 4
    if padding:
        token += '=' * (4 - padding)
    decoded = base64.urlsafe_b64decode(token).decode('utf-8')
    decoded_user_id, decoded_course_key = decoded.split(':', 1)

    assert decoded_user_id == user_id
    assert decoded_course_key == course_key


def test_direct_login_invalid_token_no_colon(fake_aws, dynamodb_local):
    """Test direct login with token that doesn't contain colon"""
    # Create invalid token (no colon separator)
    token = base64.urlsafe_b64encode(b"no-colon-here").decode('utf-8').rstrip('=')

    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )

    response = lambda_handler(event, None)
    assert response["statusCode"] == HTTP_BAD_REQUEST
    assert "Invalid token format" in response["body"]

