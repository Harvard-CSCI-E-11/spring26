import json
import pytest
import threading
import base64
import logging
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from fake_idp import create_app, ServerThread

def _rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key()
    nums = pub.public_numbers()
    import base64
    def b64u(i): return base64.urlsafe_b64encode(i.to_bytes((i.bit_length()+7)//8, 'big')).decode().rstrip("=")
    jwk = {
        "kty": "RSA",
        "n": b64u(nums.n),
        "e": b64u(nums.e),
        "alg": "RS256",
        "use": "sig",
        "kid": "test-kid-1",
    }
    return priv_pem, jwk

@pytest.fixture(scope="session")
def fake_idp_server():
    priv_pem, jwk = _rsa_keypair()
    issuer = "http://127.0.0.1:50100"  # placeholder; exact port filled after bind
    app = create_app(issuer, priv_pem, jwk)
    server = ServerThread(app)
    server.start()
    issuer = f"http://127.0.0.1:{server.port}"
    logging.getLogger().debug("issuer=%s server=%s",issuer,server)
    # Patch issuer inside app (so discovery returns correct URLs)
    app.issuer = issuer
    app.config["SERVER_NAME"] = None  # not strictly needed
    yield {
        "issuer": issuer,
        "discovery": f"{issuer}/.well-known/openid-configuration",
        "private_key_pem": priv_pem,
        "jwk": jwk,
    }
    server.stop()

@pytest.fixture
def fake_aws(monkeypatch):
    """Monkeypatch Secrets Manager + DynamoDB used by home.py."""
    from home_app import home

    class FakeSecrets:
        def get_secret_value(self, SecretId):
            # Provide exactly what home.get_odic_config expects
            secret = {
                "oidc_discovery_endpoint": pytest.discovered,
                "client_id": "client-123",
                "redirect_uri": "https://app.example.org/auth/callback",
                "hmac_secret": "super-secret-hmac",
                "secret_key": "client-secret-xyz",
            }
            return {"SecretString": json.dumps(secret)}

    class FakeTable:
        def __init__(self):
            self.db = {}
        def put_item(self, Item):
            self.db[(Item["email"], Item["sk"])] = Item
        def get_item(self, Key):
            return {"Item": self.db.get((Key["email"], Key["sk"]))}
        def delete_item(self, Key):
            self.db.pop((Key["email"], Key["sk"]), None)

    class FakeSessionsTable:
        def __init__(self):
            self.db = {}
        def put_item(self, Item):
            self.db[Item["sid"]] = Item
        def get_item(self, Key):
            return {"Item": self.db.get(Key["sid"])}
        def delete_item(self, Key):
            self.db.pop(Key["sid"], None)
        # optional scan support if you want to unit-test heartbeat locally
        def scan(self, **kwargs):
            return {"Items": list(self.db.values())}

    # capture discovery URL from test after fixture wiring
    monkeypatch.setenv("OIDC_SECRET_ID", "fake-secret-id")
    monkeypatch.setenv("DDB_REGION", "us-east-1")
    monkeypatch.setenv("DDB_TABLE_ARN", "arn:aws:dynamodb:us-east-1:000000000000:table/fake-table")
    monkeypatch.setenv("SESSIONS_TABLE_NAME", "sessions-table")
    monkeypatch.setenv("COOKIE_DOMAIN", "app.example.org")

    monkeypatch.setattr(home, "secretsmanager_client", FakeSecrets())
    monkeypatch.setattr(home, "users_table", FakeTable())
    monkeypatch.setattr(home, "sessions_table", FakeSessionsTable())
    yield
