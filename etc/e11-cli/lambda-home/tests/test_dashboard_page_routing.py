"""
Test dashboard page routing with query parameters.

This test verifies that URLs like /dashboard?page=terms.html correctly
return the appropriate template instead of always showing the dashboard.
"""

import pytest
import uuid
import home_app.home as home
import home_app.oidc as oidc
import urllib.parse
import requests
from e11.e11_common import create_new_user
from test_utils import create_lambda_event


def _get_authenticated_session(fake_idp_server):
    """Helper function to create a test user and get an authenticated session cookie"""
    from home_app.common import COOKIE_NAME
    
    # Use unique email per test run to avoid conflicts
    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    create_new_user(test_email, {"email": test_email, "name": "Test User"})
    
    # Simulate OIDC callback to get a valid session cookie
    cfg = oidc.load_openid_config(fake_idp_server["discovery"], client_id="client-123",
                                  redirect_uri="https://app.example.org/auth/callback")
    cfg["hmac_secret"] = "super-secret-hmac"
    cfg["secret_key"] = "client-secret-xyz"
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))
    
    # Call the Lambda callback to get a session
    cb_event = create_lambda_event("/auth/callback", qs=qs)
    cb_resp = home.lambda_handler(cb_event, None)
    assert cb_resp["statusCode"] == 302
    assert cb_resp["cookies"]
    
    # Extract just the name=value part from the Set-Cookie string
    # make_cookie returns "AuthSid=value; Path=/; Secure; ..." but Lambda HTTP API v2
    # expects cookies in the format ["AuthSid=value"] when receiving from client
    cookie_strings = []
    for cookie in cb_resp['cookies']:
        if cookie.startswith(f"{COOKIE_NAME}="):
            # Extract just the name=value part (before the first semicolon)
            name_value = cookie.split(';')[0]
            cookie_strings.append(name_value)
        else:
            cookie_strings.append(cookie)
    
    return cookie_strings


@pytest.mark.parametrize("page_name,expected_comment", [
    ("terms.html", "<!-- template: terms.html -->"),
    ("privacy.html", "<!-- template: privacy.html -->"),
    ("help.html", "<!-- template: help.html -->"),
    ("about.html", "<!-- template: about.html -->"),
])
def test_dashboard_page_routing(fake_idp_server, fake_aws, monkeypatch, dynamodb_local, clean_dynamodb,
                                page_name, expected_comment):
    """Test that /dashboard?page=<page> returns the correct template"""
    cookies = _get_authenticated_session(fake_idp_server)
    
    # Test /dashboard?page=<page_name>
    event = create_lambda_event("/dashboard", method="GET", 
                                 qs={"page": page_name},
                                 cookies=cookies)
    response = home.lambda_handler(event, None)
    
    assert response["statusCode"] == 200, \
        f"Expected status 200 for /dashboard?page={page_name}, got {response['statusCode']}"
    assert expected_comment in response["body"], \
        f"Response should contain {expected_comment}, but got dashboard instead. " \
        f"Response body snippet: {response['body'][:500]}"


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])

