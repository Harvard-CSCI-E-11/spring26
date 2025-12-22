import json
import os
import pytest
import base64
import logging
import boto3
import requests
from botocore.exceptions import ClientError
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

from fake_idp import create_app, ServerThread
from e11.e11core.constants import COURSE_DOMAIN
from e11.e11_common import AWS_REGION

expected_hostnames = [
    f'testcsci-e-11.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab1.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab2.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab3.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab4.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab5.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab6.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab7.{COURSE_DOMAIN}',
    f'testcsci-e-11-lab8.{COURSE_DOMAIN}'
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

# Configure boto3 to use local DynamoDB endpoint
# IMPORTANT: We use DynamoDB Local for testing, NOT monkeypatching for DynamoDB.
# Tests should create actual records in DynamoDB Local using functions like create_new_user()
# and new_session(), and query the real tables. Do NOT mock users_table.query or sessions_table.query.
DYNAMODB_LOCAL_ENDPOINT = os.environ.get('AWS_ENDPOINT_URL_DYNAMODB', 'http://localhost:8010/')

def pytest_configure(config):
    """Configure pytest to use local DynamoDB"""
    # Set environment variables if not already set
    if 'AWS_ENDPOINT_URL_DYNAMODB' not in os.environ:
        os.environ['AWS_ENDPOINT_URL_DYNAMODB'] = DYNAMODB_LOCAL_ENDPOINT
    if 'AWS_ACCESS_KEY_ID' not in os.environ:
        os.environ['AWS_ACCESS_KEY_ID'] = 'test'
    if 'AWS_SECRET_ACCESS_KEY' not in os.environ:
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'
    if 'AWS_DEFAULT_REGION' not in os.environ:
        os.environ['AWS_DEFAULT_REGION'] = AWS_REGION
    if 'USERS_TABLE_NAME' not in os.environ:
        os.environ['USERS_TABLE_NAME'] = 'e11-users'
    if 'SESSIONS_TABLE_NAME' not in os.environ:
        os.environ['SESSIONS_TABLE_NAME'] = 'home-app-sessions'

def _cleanup_dynamodb_tables(dynamodb, users_table_name, sessions_table_name):
    """Helper function to clean up all items from DynamoDB tables"""
    for table_name in [users_table_name, sessions_table_name]:
        try:
            table = dynamodb.Table(table_name)
            last_evaluated_key = None
            while True:
                scan_kwargs = {'ExclusiveStartKey': last_evaluated_key} if last_evaluated_key else {}
                scan = table.scan(**scan_kwargs)

                if scan.get('Items'):
                    with table.batch_writer() as batch:
                        for item in scan['Items']:
                            if 'user_id' in item and 'sk' in item:
                                batch.delete_item(Key={'user_id': item['user_id'], 'sk': item['sk']})
                            elif 'sid' in item:
                                batch.delete_item(Key={'sid': item['sid']})

                last_evaluated_key = scan.get('LastEvaluatedKey')
                if not last_evaluated_key:
                    break
        except Exception as e:
            logging.warning("Failed to clean up DynamoDB table %s: %s", table_name, e)


@pytest.fixture(scope="session")
def dynamodb_local():
    """Ensure local DynamoDB is running and tables exist"""
    # Check if DynamoDB Local is running
    try:
        requests.get(DYNAMODB_LOCAL_ENDPOINT, timeout=1)
    except requests.exceptions.RequestException:
        pytest.skip("DynamoDB Local is not running. Run 'make start_local_dynamodb' first.")

    dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMODB_LOCAL_ENDPOINT, region_name=AWS_REGION)

    # Create users table
    users_table_name = os.environ.get('USERS_TABLE_NAME', 'e11-users')
    try:
        table = dynamodb.Table(users_table_name)
        table.load()
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            table = dynamodb.create_table(
                TableName=users_table_name,
                KeySchema=[
                    {'AttributeName': 'user_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'sk', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'user_id', 'AttributeType': 'S'},
                    {'AttributeName': 'sk', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'GSI_Email',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            table.wait_until_exists()

    # Create sessions table
    sessions_table_name = os.environ.get('SESSIONS_TABLE_NAME', 'home-app-sessions')
    try:
        table = dynamodb.Table(sessions_table_name)
        table.load()
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            table = dynamodb.create_table(
                TableName=sessions_table_name,
                KeySchema=[
                    {'AttributeName': 'sid', 'KeyType': 'HASH'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'sid', 'AttributeType': 'S'},
                    {'AttributeName': 'email', 'AttributeType': 'S'}
                ],
                GlobalSecondaryIndexes=[
                    {
                        'IndexName': 'GSI_Email',
                        'KeySchema': [
                            {'AttributeName': 'email', 'KeyType': 'HASH'}
                        ],
                        'Projection': {'ProjectionType': 'ALL'}
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            table.wait_until_exists()

    yield dynamodb

    # Final cleanup at end of session
    _cleanup_dynamodb_tables(dynamodb, users_table_name, sessions_table_name)


@pytest.fixture(scope="function")
def clean_dynamodb(dynamodb_local):
    """Fixture that ensures DynamoDB tables are clean before each test"""
    users_table_name = os.environ.get('USERS_TABLE_NAME', 'e11-users')
    sessions_table_name = os.environ.get('SESSIONS_TABLE_NAME', 'home-app-sessions')
    
    # Clean up before test
    _cleanup_dynamodb_tables(dynamodb_local, users_table_name, sessions_table_name)
    
    yield
    
    # Clean up after test
    _cleanup_dynamodb_tables(dynamodb_local, users_table_name, sessions_table_name)

@pytest.fixture
def fake_aws(monkeypatch, dynamodb_local, fake_idp_server):
    """
    Set up fake Secrets Manager and configure DynamoDB to use local endpoint.
    
    IMPORTANT: This fixture patches AWS service clients (Route53, SES, S3) but uses
    REAL DynamoDB Local tables. Do NOT mock DynamoDB operations - create actual
    records in DynamoDB Local and query the real tables.
    """
    from e11 import e11_common

    class FakeSecrets:
        def __init__(self, discovery_url):
            self.discovery_url = discovery_url

        def get_secret_value(self, SecretId):
            # Handle OIDC secrets
            if "oidc" in SecretId.lower() or SecretId == "fake-secret-id":
                secret = {
                    "oidc_discovery_endpoint": self.discovery_url,
                    "client_id": "client-123",
                    "redirect_uri": "https://app.example.org/auth/callback",
                    "hmac_secret": "super-secret-hmac",
                    "secret_key": "client-secret-xyz",
                }
                return {"SecretString": json.dumps(secret)}
            # Handle SSH secrets
            elif "ssh" in SecretId.lower() or SecretId == "fake-ssh-secret-id":
                return {"SecretString": json.dumps({"cscie-bot": "fake-ssh-key-pem"})}
            # Default fallback
            return {"SecretString": json.dumps({})}

    class FakeRoute53:
        def list_resource_record_sets(self, **kwargs):
            # Return empty list - no existing records
            return {"ResourceRecordSets": []}

        def change_resource_record_sets(self, **kwargs):
            # Return success response
            return {"ChangeInfo": {"Id": "fake-change-id", "Status": "PENDING"}}

    class FakeS3:
        def generate_presigned_post(self, **kwargs):
            return {"url": "https://fake-s3-url", "fields": {}}

        def generate_presigned_url(self, **kwargs):
            return "https://fake-s3-presigned-url"

        def head_object(self, **kwargs):
            return {"ContentLength": 0}

    def fake_send_email(to_addr, email_subject, email_body):
        # Mock send_email function
        return {"MessageId": "fake-message-id"}

    # Configure DynamoDB to use local endpoint
    monkeypatch.setenv("OIDC_SECRET_ID", "fake-secret-id")
    monkeypatch.setenv("SSH_SECRET_ID", "fake-ssh-secret-id")
    monkeypatch.setenv("COOKIE_DOMAIN", "app.example.org")

    # Recreate DynamoDB clients with local endpoint
    dynamodb_resource = boto3.resource('dynamodb', endpoint_url=DYNAMODB_LOCAL_ENDPOINT, region_name=AWS_REGION)
    users_table = dynamodb_resource.Table(os.environ.get('USERS_TABLE_NAME', 'e11-users'))
    sessions_table = dynamodb_resource.Table(os.environ.get('SESSIONS_TABLE_NAME', 'home-app-sessions'))

    fake_route53 = FakeRoute53()
    fake_s3 = FakeS3()

    monkeypatch.setattr(e11_common, "secretsmanager_client", FakeSecrets(fake_idp_server["discovery"]))
    monkeypatch.setattr(e11_common, "dynamodb_resource", dynamodb_resource)
    monkeypatch.setattr(e11_common, "users_table", users_table)
    monkeypatch.setattr(e11_common, "sessions_table", sessions_table)
    monkeypatch.setattr(e11_common, "route53_client", fake_route53)
    monkeypatch.setattr(e11_common, "send_email", fake_send_email)
    monkeypatch.setattr(e11_common, "s3_client", fake_s3)

    # Also patch the modules that import these directly
    import home_app.sessions as sessions_module
    monkeypatch.setattr(sessions_module, "sessions_table", sessions_table)

    # Patch home.py's direct imports (home.py imports users_table from e11_common)
    import home_app.home as home_module
    monkeypatch.setattr(home_module, "users_table", users_table)

    # Patch api.py's direct imports
    import home_app.api as api_module
    monkeypatch.setattr(api_module, "users_table", users_table)
    monkeypatch.setattr(api_module, "sessions_table", sessions_table)
    monkeypatch.setattr(api_module, "route53_client", fake_route53)
    monkeypatch.setattr(api_module, "send_email", fake_send_email)
    monkeypatch.setattr(api_module, "s3_client", fake_s3)

    yield
