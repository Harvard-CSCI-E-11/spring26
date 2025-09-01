import urllib.parse
import requests
import pytest

import home_app.oidc as oidc

def test_end_to_end_oidc_stateless(fake_idp_server, monkeypatch):
    # Wire discovery URL for fake_aws fixture
    import pytest as _pytest
    _pytest.discovered = fake_idp_server["discovery"]

    # Build openid_config like home.get_odic_config() would
    cfg = oidc.load_openid_config(
        fake_idp_server["discovery"],
        client_id="client-123",
        redirect_uri="https://app.example.org/auth/callback",
    )
    # include HMAC + client secret the way your code expects
    cfg["hmac_secret"] = "super-secret-hmac"
    cfg["secret_key"] = "client-secret-xyz"

    # Step 1: build authorization URL
    auth_url, _issued = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)

    # Step 2: simulate user hitting IdP and getting redirected back with code/state
    r = requests.get(auth_url, allow_redirects=False)
    assert r.status_code in (301, 302)
    loc = r.headers["Location"]
    parsed = urllib.parse.urlparse(loc)
    qs = dict(urllib.parse.parse_qsl(parsed.query))
    assert "code" in qs and "state" in qs

    # Step 3: exchange code and verify id_token
    result = oidc.handle_oidc_redirect_stateless(
        openid_config=cfg,
        callback_params={"code": qs["code"], "state": qs["state"]},
    )
    claims = result["claims"]
    assert claims["email"] == "alice@example.edu"
    assert claims["name"] == "Alice Example"
