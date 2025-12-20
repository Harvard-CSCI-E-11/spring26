import urllib.parse
import requests
import logging

import home_app.home as home
import home_app.oidc as oidc
from e11.e11_common import create_new_user

from test_utils import create_lambda_event

def test_lambda_routes_without_aws(fake_idp_server, fake_aws, monkeypatch, dynamodb_local):
    # Create a test user in DynamoDBLocal
    test_email = "test@example.com"
    create_new_user(test_email, {"email": test_email, "name": "Test User"})

    # 1) GET "/" should embed login URL
    resp = home.lambda_handler(create_lambda_event("/"), None)
    assert resp["statusCode"] == 200
    assert "harvard_key" in resp["body"] or "http" in resp["body"]

    # 2) Simulate full OIDC redirect:
    # Build auth URL from the same config to get a valid state
    cfg = oidc.load_openid_config(fake_idp_server["discovery"], client_id="client-123",
                                  redirect_uri="https://app.example.org/auth/callback")
    cfg["hmac_secret"] = "super-secret-hmac"
    cfg["secret_key"]  = "client-secret-xyz"
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))

    # 3) Call the Lambda callback with the returned code/state
    cb_event = create_lambda_event("/auth/callback", qs=qs)
    cb_resp  = home.lambda_handler(cb_event, None)
    print("cb_resp=",cb_resp)

    assert cb_resp["statusCode"] == 302
    assert cb_resp["headers"]["Location"] == "/dashboard"
    # cookie should be set
    assert cb_resp["cookies"]

    # 4) Dashboard route without cookies
    dash_resp = home.lambda_handler(create_lambda_event("/dashboard"), None)
    logging.getLogger().debug("dash_resp without cookies=%s",dash_resp)
    assert dash_resp["statusCode"] == 302 and dash_resp['headers']['Location']=='/'

    # 4) Dashboard route with cookies
    dash_resp = home.lambda_handler(create_lambda_event("/dashboard", cookies=cb_resp['cookies']), None)
    logging.getLogger().debug("dash_resp with cookies (%s) = %s",cb_resp['cookies'],dash_resp)
    logging.getLogger().warning("Not validating dashboard logging. Requires DynamoDBLocal data")

    # 5) Logout route
    logout_resp = home.lambda_handler(create_lambda_event("/logout"), None)
    logging.getLogger().debug("logout_resp=%s",logout_resp)
    assert logout_resp["statusCode"] == 200
    assert "Max-Age=0;" in logout_resp['cookies'][0] # validate that it logs the user out
    assert "You have been logged out" in logout_resp['body']

    # 6) Check point
    from e11.e11core.constants import API_PATH
    home.lambda_handler(create_lambda_event(API_PATH, method='POST', body='{"action":"ping"}'), None)
