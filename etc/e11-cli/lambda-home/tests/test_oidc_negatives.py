import urllib.parse
import time
import requests

import pytest
from itsdangerous import BadSignature, SignatureExpired

import home_app.oidc as oidc

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
    # Corrupt the state (break signature) by replacing the last several characters
    # This ensures we corrupt the signature portion, not just the payload
    original_state = qs["state"]
    # Replace the last 10 characters (or all if shorter) with garbage to reliably break the signature
    # URLSafeTimedSerializer creates payload.signature format, so corrupting the end breaks the signature
    corrupt_length = min(10, len(original_state))
    bad_state = original_state[:-corrupt_length] + "X" * corrupt_length
    with pytest.raises(BadSignature) as e:
        oidc.handle_oidc_redirect_stateless(
            openid_config=cfg,
            callback_params={"code": qs["code"], "state": bad_state},
        )
    assert "Signature" in str(e.value)

def test_expired_state(fake_idp_server):
    cfg = _build_cfg(fake_idp_server["discovery"])
    auth_url, _ = oidc.build_oidc_authorization_url_stateless(openid_config=cfg)
    r = requests.get(auth_url, allow_redirects=False)
    qs = dict(urllib.parse.parse_qsl(urllib.parse.urlparse(r.headers["Location"]).query))
    # Add a delay to ensure the state expires
    time.sleep(2)  # Wait 2 seconds
    # Force expiry by setting max_state_age_seconds to a very small value
    with pytest.raises(SignatureExpired) as e:
        oidc.handle_oidc_redirect_stateless(
            openid_config=cfg,
            callback_params={"code": qs["code"], "state": qs["state"]},
            max_state_age_seconds=1,  # 1 second should expire after 2 second delay
        )
    assert "age" in str(e.value).lower()

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
