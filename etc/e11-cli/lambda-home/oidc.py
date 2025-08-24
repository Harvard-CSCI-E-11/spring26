"""
oidc implementation
"""

import base64
import hashlib
import secrets
import time
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

import requests
import jwt
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from common import LOGGER


# Helper: stateless state serializer
def _state_serializer(secret_key: str) -> URLSafeTimedSerializer:
    # Change salt to rotate state format without changing your secret
    return URLSafeTimedSerializer(secret_key=secret_key, salt="oidc-state-v1")


def load_openid_config(discovery_url: str, *, client_id: str, redirect_uri: str) -> dict:
    """Fetch the contents of the discovery URL and create the openid config"""
    r = requests.get(discovery_url, timeout=10)
    r.raise_for_status()
    d = r.json()
    return {
        "issuer": d["issuer"],
        "authorization_endpoint": d["authorization_endpoint"],  # e.g. https://login.harvard.edu/oauth2/v1/authorize
        "token_endpoint": d["token_endpoint"],
        "jwks_uri": d["jwks_uri"],
        "client_id": client_id,
        "redirect_uri": redirect_uri,
    }


# -------- Function #1: Build Authorization URL (stateless) --------
# pylint: disable=too-many-locals
def build_oidc_authorization_url_stateless( *, openid_config: dict, scope=("openid", "profile", "email"), state_ttl_seconds=600 ):
    """
    Returns (authorization_url, issued_at_epoch) with state carrying nonce+PKCE code_verifier (signed).
    openid_config requires: authorization_endpoint, client_id, redirect_uri
    """
    auth_endpoint = openid_config["authorization_endpoint"]
    client_id     = openid_config["client_id"]
    redirect_uri  = openid_config["redirect_uri"]

    # PKCE
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).decode().rstrip("=")
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")

    # CSRF + replay
    nonce = base64.urlsafe_b64encode(secrets.token_bytes(24)).decode().rstrip("=")
    issued_at = int(time.time())

    # Sign the state (contains only what's needed later)
    s = _state_serializer(openid_config['hmac_secret'])
    state_payload = {"nonce": nonce, "cv": code_verifier, "iat": issued_at, "ttl": state_ttl_seconds}
    state = s.dumps(state_payload)

    query = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": " ".join(scope),
        "state": state,
        "nonce": nonce,  # required so provider reflects it in ID token
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    parts = list(urlparse(auth_endpoint))
    existing = dict(parse_qsl(parts[4], keep_blank_values=True))
    existing.update(query)
    parts[4] = urlencode(existing)
    return urlunparse(parts), issued_at


# -------- Function #2: Handle Redirect (stateless) --------
# pylint: disable=too-many-locals
def handle_oidc_redirect_stateless(
    *,
    openid_config: dict,      # must include: token_endpoint, issuer, jwks_uri, client_id, redirect_uri
    callback_params: dict,    # API Gateway query params (GET)
    max_state_age_seconds=600 ):
    """
    Verifies signed state (age-limited), exchanges code with PKCE, verifies ID token, returns claims.
    """
    # 1) Validate redirect params
    if "error" in callback_params:
        raise RuntimeError(f"OIDC error: {callback_params.get('error')} - {callback_params.get('error_description')}")
    code  = callback_params.get("code")
    state = callback_params.get("state")
    if not code or not state:
        raise RuntimeError("Missing 'code' or 'state'.")

    # 2) Unpack & verify state (stateless)
    s = _state_serializer(openid_config['hmac_secret'])
    try:
        st = s.loads(state, max_age=max_state_age_seconds)
    except SignatureExpired as e:
        LOGGER.info("SignatureExpired: %s",e)
        raise
    except BadSignature as e:
        LOGGER.info("BadSignature: %s",e)
        raise

    code_verifier = st["cv"]
    expected_nonce = st["nonce"]

    token_endpoint = openid_config["token_endpoint"]
    issuer         = openid_config["issuer"]
    jwks_uri       = openid_config["jwks_uri"]
    client_id      = openid_config["client_id"]
    redirect_uri   = openid_config["redirect_uri"]
    client_secret  = openid_config['secret_key']

    # 3) Token exchange (confidential client with PKCE)
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,          # some IdPs require it even with Basic auth
        "client_secret": client_secret,
        "code_verifier": code_verifier,  # binds the code to our request
    }
    resp = requests.post(token_endpoint, data=data, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"Token endpoint error {resp.status_code}: {resp.text}")
    token_set = resp.json()

    id_token = token_set.get("id_token")
    if not id_token:
        raise RuntimeError("No id_token in token response.")
    access_token = token_set.get("access_token")

    # 4) Verify ID token (sig, iss, aud) and nonce
    jwk_client = jwt.PyJWKClient(jwks_uri)
    signing_key = jwk_client.get_signing_key_from_jwt(id_token)
    claims = jwt.decode(
        id_token,
        signing_key.key,
        algorithms=["RS256", "ES256", "PS256", "RS384", "ES384", "PS384", "RS512", "ES512", "PS512"],
        audience=client_id,
        issuer=issuer,
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    if claims.get("nonce") != expected_nonce:
        raise RuntimeError("Nonce mismatch.")

    # 5) Minimal profile/email extraction
    user = {
        "sub": claims.get("sub"),
        "email": claims.get("email"),
        "email_verified": claims.get("email_verified"),
        "name": claims.get("name"),
        "given_name": claims.get("given_name"),
        "family_name": claims.get("family_name"),
        "preferred_username": claims.get("preferred_username"),
        "updated_at": claims.get("updated_at"),
    }

    return {
        "id_token": id_token,
        "access_token": access_token,
        "expires_in": token_set.get("expires_in"),
        "scope": token_set.get("scope"),
        "token_type": token_set.get("token_type"),
        "claims": user,
    }
