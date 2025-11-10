import json
import pytest
import base64
import logging
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from fake_idp import create_app, ServerThread

expected_hostnames = [
    'testcsci-e-11.csci-e-11.org',
    'testcsci-e-11-lab1.csci-e-11.org',
    'testcsci-e-11-lab2.csci-e-11.org',
    'testcsci-e-11-lab3.csci-e-11.org',
    'testcsci-e-11-lab4.csci-e-11.org',
    'testcsci-e-11-lab5.csci-e-11.org',
    'testcsci-e-11-lab6.csci-e-11.org',
    'testcsci-e-11-lab7.csci-e-11.org',
    'testcsci-e-11-lab8.csci-e-11.org'
]


def _rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    pub = key.public_key()
    nums = pub.public_numbers()
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
    from home_app import common

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
            # For GSI support, maintain a separate index
            self.gsi_email_index = {}

        def put_item(self, Item):
            # Handle different key structures
            if "email" in Item and "sk" in Item:
                self.db[(Item["email"], Item["sk"])] = Item
                # Also add to GSI index if email exists
                self.gsi_email_index[Item["email"]] = Item
            elif "user_id" in Item and "sk" in Item:
                # For log entries that use user_id instead of email
                self.db[(Item["user_id"], Item["sk"])] = Item
            else:
                # Fallback for other cases
                key = tuple(sorted(Item.items()))
                self.db[key] = Item

        def get_item(self, Key):
            # Handle different key structures
            if "email" in Key and "sk" in Key:
                return {"Item": self.db.get((Key["email"], Key["sk"]))}
            elif "user_id" in Key and "sk" in Key:
                return {"Item": self.db.get((Key["user_id"], Key["sk"]))}
            else:
                # Fallback for other cases
                key = tuple(sorted(Key.items()))
                return {"Item": self.db.get(key)}

        def delete_item(self, Key):
            # Handle different key structures
            if "email" in Key and "sk" in Key:
                self.db.pop((Key["email"], Key["sk"]), None)
            elif "user_id" in Key and "sk" in Key:
                self.db.pop((Key["user_id"], Key["sk"]), None)
            else:
                # Fallback for other cases
                key = tuple(sorted(Key.items()))
                self.db.pop(key, None)

        def update_item(self, Key, UpdateExpression, ExpressionAttributeValues):
            # Simple implementation for testing
            key_tuple = (Key["user_id"], Key["sk"])
            if key_tuple in self.db:
                item = self.db[key_tuple]
                # Apply updates based on UpdateExpression
                if "SET public_ip = :ip, hostname = :hn, host_registered = :t, name = :name" in UpdateExpression:
                    item["public_ip"] = ExpressionAttributeValues[":ip"]
                    item["hostname"] = ExpressionAttributeValues[":hn"]
                    item["host_registered"] = ExpressionAttributeValues[":t"]
                    item["name"] = ExpressionAttributeValues[":name"]

        def query(self, **kwargs):
            items = []

            # Handle GSI queries
            if kwargs.get("IndexName") == "GSI_Email":
                _key_condition = kwargs.get("KeyConditionExpression")

                # For GSI queries, we need to extract the email from the Key condition
                # The condition will be something like Key("email").eq(email)
                # We'll look for items with matching email
                for (_email, _sk), item in self.db.items():
                    if "email" in item:
                        items.append(item)
                        break  # GSI should only return one item per email

            # Handle regular queries
            else:
                _key_condition = kwargs.get("KeyConditionExpression")

                # Handle Key(USER_ID).eq(user_id) case
                # We'll look for items with matching user_id
                for (email, sk), item in self.db.items():
                    if "user_id" in item:
                        items.append(item)

                # Handle complex conditions like Key(USER_ID).eq(user_id) & Key('sk').begins_with('log#')
                # For now, we'll return all items and let the application filter
                if not items:
                    items = list(self.db.values())

            # Handle pagination
            exclusive_start_key = kwargs.get("ExclusiveStartKey")
            if exclusive_start_key:
                # Simple pagination - just return empty for now
                items = []

            return {
                "Items": items,
                "Count": len(items),
                "LastEvaluatedKey": None if len(items) < 10 else "fake_last_key"
            }

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

        def query(self, **kwargs):
            items = []
            key_condition = kwargs.get("KeyConditionExpression")
            if key_condition == "email = :e":
                email = kwargs.get("ExpressionAttributeValues", {}).get(":e")
                for item in self.db.values():
                    if item.get("email") == email:
                        items.append(item)

            return {
                "Items": items,
                "Count": len(items),
                "LastEvaluatedKey": None
            }

    # capture discovery URL from test after fixture wiring
    monkeypatch.setenv("OIDC_SECRET_ID", "fake-secret-id")
    monkeypatch.setenv("DDB_REGION", "us-east-1")
    monkeypatch.setenv("DDB_TABLE_ARN", "arn:aws:dynamodb:us-east-1:000000000000:table/fake-table")
    monkeypatch.setenv("SESSIONS_TABLE_NAME", "sessions-table")
    monkeypatch.setenv("COOKIE_DOMAIN", "app.example.org")

    monkeypatch.setattr(common, "secretsmanager_client", FakeSecrets())
    monkeypatch.setattr(home, "users_table", FakeTable())
    monkeypatch.setattr(home, "sessions_table", FakeSessionsTable())
    yield
