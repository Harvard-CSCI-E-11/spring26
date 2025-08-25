import urllib.parse
import time
import requests
import oidc
import pytest

def _build_cfg(discovery, *, client_id="client-123", redirect_uri="https://app.example.org/auth/callback"):
    cfg = oidc.load_openid_config(discovery, client_id=client_id, redirect_uri=redirect_uri)
    cfg["hmac_secret"] = "super-secret-hmac"
    cfg["secret_key"] = "client-secret-xyz"
    return cfg

def test_invalid_state_signature(fake_idp_server):
    cfg = _build_cfg(fake_idp_server["discovery"])
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))
    # Corrupt the state (break signature)
    bad_state = qs["state"][:-1] + ("A" if qs["state"][-1] != "A" else "B")
    with pytest.raises(RuntimeError) as e:
        oidc.handle_oidc_redirect_stateless(
            openid_config=cfg,
            callback_params={"code": qs["code"], "state": bad_state},
        )
    assert "Invalid state signature" in str(e.value)

def test_expired_state(fake_idp_server):
    cfg = _build_cfg(fake_idp_server["discovery"])
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))
    # Force expiry by setting max_state_age_seconds=0
    with pytest.raises(RuntimeError) as e:
        oidc.handle_oidc_redirect_stateless(
            openid_config=cfg,
            callback_params={"code": qs["code"], "state": qs["state"]},
            max_state_age_seconds=0,
        )
    assert "State expired" in str(e.value)

def test_pkce_mismatch_with_swapped_state(fake_idp_server):
    # Issue two separate auth requests; use code from #1 with state from #2 → PKCE fail
    cfg = _build_cfg(fake_idp_server["discovery"])
    a1, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    a2, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)

    r1 = requests.get(a1, allow_redirects=False)
    r2 = requests.get(a2, allow_redirects=False)
    qs1 = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r1.headers["Location"]).query))
    qs2 = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r2.headers["Location"]).query))

    with pytest.raises(RuntimeError) as e:
        oidc.handle_oidc_redirect_stateless(
            openid_config=cfg,
            callback_params={"code": qs1["code"], "state": qs2["state"]},
        )
    # Our fake IdP returns 400 with pkce verification failed → surfaces as Token endpoint error 400
    assert "Token endpoint error 400" in str(e.value)
