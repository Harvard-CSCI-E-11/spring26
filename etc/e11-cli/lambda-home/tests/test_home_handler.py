import urllib.parse
import requests
import home
import oidc

def _api_event(path, qs=None):
    return {
        "rawPath": path,
        "queryStringParameters": qs or {},
        "requestContext": {"http": {"method": "GET", "sourceIp": "203.0.113.9"}, "stage": ""},
        "isBase64Encoded": False,
        "body": None,
    }

def test_lambda_routes_without_aws(fake_idp_server, fake_aws, monkeypatch):
    # Make home.get_odic_config() discovery point to our fake IdP
    import tests.conftest as cf
    # Patch the secret fixture to point at the fake IdP
    import json
    class PatchedSecrets:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({
                "oidc_discovery_endpoint": fake_idp_server["discovery"],
                "client_id": "client-123",
                "redirect_uri": "https://app.example.org/auth/callback",
                "hmac_secret": "super-secret-hmac",
                "secret_key": "client-secret-xyz",
            })}
    monkeypatch.setattr(home, "_boto_secrets", PatchedSecrets())

    # 1) GET "/" should embed login URL
    resp = home.lambda_handler(_api_event("/"), None)
    assert resp["statusCode"] == 200
    assert "harvard_key" in resp["body"] or "http" in resp["body"]

    # 2) Simulate full OIDC redirect:
    # Build auth URL from the same config to get a valid state
    cfg = oidc.load_openid_config(fake_idp_server["discovery"], client_id="client-123",
                                  redirect_uri="https://app.example.org/auth/callback")
    cfg["hmac_secret"] = "super-secret-hmac"
    cfg["secret_key"] = "client-secret-xyz"
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))

    # 3) Call the Lambda callback with the returned code/state
    cb_event = _api_event("/auth/callback", qs=qs)
    cb_resp = home.lambda_handler(cb_event, None)
    assert cb_resp["statusCode"] == 302
    assert cb_resp["headers"]["Location"] == "/dashboard"
    # cookie should be set
    assert cb_resp["cookies"]

    # 4) Dashboard route
    dash_resp = home.lambda_handler(_api_event("/dashboard"), None)
    assert dash_resp["statusCode"] == 200

    # 5) Logout route
    logout_resp = home.lambda_handler(_api_event("/logout"), None)
    assert logout_resp["statusCode"] == 200
