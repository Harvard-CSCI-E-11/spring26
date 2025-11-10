"""
Common test utilities to eliminate redundancy across test files.
This module consolidates AWS mock classes, test data factories, and assertion helpers.
"""

import logging
import json
import os
import tempfile
import configparser
from typing import Dict, Any, List, Optional


logger = logging.getLogger()


class MockedAWSServices:
    """Consolidated AWS services mock for testing registration API and other AWS-dependent functionality"""

    def __init__(self):
        self.dynamodb_items = {}
        self.route53_changes = []
        self.ses_emails = []    # list of sent mails
        self.secrets = {}

    def setup_mocks(self, monkeypatch):
        """Setup all AWS service mocks"""

        # Mock DynamoDB
        class MockDynamoDBTable:
            def __init__(self, mock_aws):
                self.mock_aws = mock_aws

            def put_item(self, Item):
                key = (Item.get('user_id'), Item.get('sk', '#'))
                self.mock_aws.dynamodb_items[key] = Item
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}

            def get_item(self, Key):
                key = (Key.get('user_id'), Key.get('sk', '#'))
                item = self.mock_aws.dynamodb_items.get(key)
                return {'Item': item} if item else {}

            def update_item(self, Key, UpdateExpression, ExpressionAttributeValues):
                key = (Key.get('user_id'), Key.get('sk', '#'))
                if key in self.mock_aws.dynamodb_items:
                    # Simulate the update
                    item = self.mock_aws.dynamodb_items[key]
                    # Parse the update expression and apply changes
                    for attr_name, attr_value in ExpressionAttributeValues.items():
                        if attr_name == ':ip':
                            item['ip_address'] = attr_value
                        elif attr_name == ':hn':
                            item['hostname'] = attr_value
                        elif attr_name == ':t':
                            item['host_registered'] = attr_value
                        elif attr_name == ':name':
                            item['name'] = attr_value
                        elif attr_name == ':preferred_name':
                            item['preferred_name'] = attr_value
                else:
                    # Create a new item if it doesn't exist
                    item = {
                        'user_id': Key.get('user_id'),
                        'sk': Key.get('sk', '#'),
                        'ip_address': ExpressionAttributeValues.get(':ip'),
                        'hostname': ExpressionAttributeValues.get(':hn'),
                        'host_registered': ExpressionAttributeValues.get(':t'),
                        'preferred_name': ExpressionAttributeValues.get(':preferred_name')
                    }
                    self.mock_aws.dynamodb_items[key] = item
                return {'ResponseMetadata': {'HTTPStatusCode': 200}}

            def query(self, **kwargs):
                # Mock query for GSI_Email index
                if kwargs.get('IndexName') == 'GSI_Email':
                    email = kwargs.get('KeyConditionExpression', '').split('=')[-1].strip()
                    # Find items with matching email
                    items = []
                    for item in self.mock_aws.dynamodb_items.values():
                        if item.get('email') == email:
                            items.append(item)
                    return {'Items': items, 'Count': len(items)}
                return {'Items': [], 'Count': 0}

        # Mock Route53
        class MockRoute53:
            def __init__(self, mock_aws):
                self.mock_aws = mock_aws

            def list_resource_record_sets(self, HostedZoneId, StartRecordName, StartRecordType, MaxItems):
                return {'ResourceRecordsSets':[]}

            def change_resource_record_sets(self, HostedZoneId, ChangeBatch):
                self.mock_aws.route53_changes.append({
                    'HostedZoneId': HostedZoneId,
                    'ChangeBatch': ChangeBatch
                })
                return {
                    'ChangeInfo': {
                        'Id': 'test-change-id',
                        'Status': 'PENDING',
                        'SubmittedAt': '2024-01-01T00:00:00Z'
                    }
                }

        # Mock SES
        class MockSES:
            def __init__(self, mock_aws):
                self.mock_aws = mock_aws

            def send_email(self, Source, Destination, Message):
                self.mock_aws.ses_emails.append({
                    'Source': Source,
                    'Destination': Destination,
                    'Message': Message
                })
                return {
                    'MessageId': 'test-message-id',
                    'ResponseMetadata': {'HTTPStatusCode': 200}
                }

        # Mock Secrets Manager
        class MockSecretsManager:
            def __init__(self, mock_aws):
                self.mock_aws = mock_aws

            def get_secret_value(self, SecretId):
                secret = self.mock_aws.secrets.get(SecretId, {
                    "oidc_discovery_endpoint": "https://fake-discovery.example.com",
                    "client_id": "fake-client-id",
                    "redirect_uri": "https://fake-app.example.com/auth/callback",
                    "hmac_secret": "fake-hmac-secret",
                    "secret_key": "fake-secret-key",
                })
                return {'SecretString': json.dumps(secret)}

        # Apply mocks
        import home_app.home as home
        import home_app.common as common

        monkeypatch.setattr(home, 'users_table', MockDynamoDBTable(self))
        monkeypatch.setattr(common, 'users_table', MockDynamoDBTable(self))
        monkeypatch.setattr(home, 'route53_client', MockRoute53(self))
        monkeypatch.setattr(home, 'ses_client', MockSES(self))
        monkeypatch.setattr(common, 'secretsmanager_client', MockSecretsManager(self))

        # Set environment variables
        monkeypatch.setenv('OIDC_SECRET_ID', 'fake-secret-id')
        monkeypatch.setenv('DDB_REGION', 'us-east-1')
        monkeypatch.setenv('DDB_USERS_TABLE_ARN', 'arn:aws:dynamodb:us-east-1:000000000000:table/fake-users-table')
        monkeypatch.setenv('SESSIONS_TABLE_NAME', 'fake-sessions-table')
        monkeypatch.setenv('COOKIE_DOMAIN', 'csci-e-11.org')
        monkeypatch.setenv('HOSTED_ZONE_ID', 'Z05034072HOMXYCK23BRA')


class MockedSessionsTable:
    """Mock sessions table for testing"""

    def __init__(self):
        self.db = {}

    def put_item(self, Item):
        self.db[Item["sid"]] = Item

    def get_item(self, Key):
        return {"Item": self.db.get(Key["sid"])}

    def delete_item(self, Key):
        self.db.pop(Key["sid"], None)

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


# Test Data Factories
def create_test_config_data(**overrides) -> Dict[str, Any]:
    """Create standardized test configuration data"""
    default_data = {
        'preferred_name': 'Test User',
        'email': 'test@csci-e-11.org',
        'course_key': '123456',
        'public_ip': '1.2.3.4',
        'instanceId': 'i-1234567890abcdef0'
    }
    default_data.update(overrides)
    return default_data


def create_test_auth_data(**overrides) -> Dict[str, Any]:
    """Create standardized test authentication data"""
    default_data = {
        'email': 'test@csci-e-11.org',
        'course_key': '123456'
    }
    default_data.update(overrides)
    return default_data


def create_registration_payload(config_data: Dict[str, Any], auth_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create standardized registration payload"""
    return {
        'action': 'register',
        'auth': auth_data,
        'registration': config_data
    }


def create_lambda_event(path: str, method: str = 'GET', body: Optional[str] = None,
                       qs: Optional[Dict] = None, cookies: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create standardized Lambda event for testing"""
    return {
        "rawPath": path,
        "queryStringParameters": qs or {},
        "requestContext": {"http": {"method": method, "sourceIp": "203.0.113.9"}, "stage": ""},
        "isBase64Encoded": False,
        "body": body,
        "cookies": cookies or []
    }


def create_test_config_file(config_data: Dict[str, Any]) -> str:
    """Create a temporary config file with test data"""
    config = configparser.ConfigParser()
    config['student'] = config_data

    # Create temporary file
    fd, path = tempfile.mkstemp(suffix='.ini')
    os.close(fd)

    with open(path, 'w') as f:
        config.write(f)

    return path


# Assertion Helpers
def assert_dynamodb_updated(mock_aws: MockedAWSServices, user_id: str, expected_data: Dict[str, Any]):
    """Assert that DynamoDB was updated with expected data"""
    user_update_found = False
    for key, item in mock_aws.dynamodb_items.items():
        if key[0] == user_id and key[1] == '#':
            for field, expected_value in expected_data.items():
                assert item.get(field) == expected_value, f"Expected {field}={expected_value}, got {item.get(field)}"
            user_update_found = True
            break

    assert user_update_found, f"User record for {user_id} was not updated in DynamoDB"


def assert_route53_called(mock_aws: MockedAWSServices, expected_hostnames: List[str], expected_ip: str = '1.2.3.4'):
    """Assert that Route53 was called with expected hostnames"""
    assert len(mock_aws.route53_changes) == 1, f"Expected 1 Route53 call, got {len(mock_aws.route53_changes)}"

    route53_change = mock_aws.route53_changes[0]
    assert route53_change['HostedZoneId'] == 'Z05034072HOMXYCK23BRA'

    changes = route53_change['ChangeBatch']['Changes']
    if len(changes) != len(expected_hostnames):
        logger.error("changes=%s",json.dumps(changes,indent=4,default=str))
        logger.error("expected_hostnames=%s",json.dumps(expected_hostnames,indent=4,default=str))
    assert len(changes) == len(expected_hostnames), f"Expected {len(expected_hostnames)} DNS changes, got {len(changes)}"

    for change in changes:
        assert change['Action'] == 'UPSERT'
        assert change['ResourceRecordSet']['Type'] == 'A'
        assert change['ResourceRecordSet']['TTL'] == 300
        assert change['ResourceRecordSet']['ResourceRecords'][0]['Value'] == expected_ip
        assert change['ResourceRecordSet']['Name'] in expected_hostnames


def assert_ses_email_sent(mock_aws: MockedAWSServices, expected_recipient: str, expected_subject_contains: str = None):
    """Assert that SES email was sent with expected recipient"""
    for msg in mock_aws.ses_emails:
        logger.debug("msg=%s",json.dumps(msg,indent=4,default=str))
        if msg['Source'] == 'admin@csci-e-11.org':
            if (expected_subject_contains in msg['Message']['Subject']['Data'] and
                expected_recipient in msg['Destination']['ToAddresses']):
                return

    logger.error("Could not find %s/%s in ses_emails: %s",expected_subject_contains,expected_recipient,json.dumps(mock_aws.ses_emails,indent=4,default=str))


def assert_response_success(response: Dict[str, Any], expected_message_contains: str = None):
    """Assert that API response indicates success"""
    assert response['statusCode'] == 200, f"Expected status 200, got {response['statusCode']}"

    if expected_message_contains:
        response_body = json.loads(response['body'])
        assert expected_message_contains in response_body['message']


def assert_response_error(response: Dict[str, Any], expected_status: int, expected_message_contains: str = None):
    """Assert that API response indicates an error"""
    assert response['statusCode'] == expected_status, f"Expected status {expected_status}, got {response['statusCode']}"

    if expected_message_contains:
        response_body = json.loads(response['body'])
        assert expected_message_contains in response_body.get('message', '')


# Environment Setup Helpers
def setup_aws_mocks(monkeypatch, **config):
    """Setup AWS mocks with optional configuration"""
    mock_aws = MockedAWSServices()
    mock_aws.setup_mocks(monkeypatch)
    return mock_aws


def setup_oidc_mocks(monkeypatch, fake_idp_server):
    """Setup OIDC-specific mocks"""
    import home_app.common as common

    class FakeSecrets:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({
                "oidc_discovery_endpoint": fake_idp_server["discovery"],
                "client_id": "client-123",
                "redirect_uri": "https://app.example.org/auth/callback",
                "hmac_secret": "super-secret-hmac",
                "secret_key": "client-secret-xyz",
            })}

    monkeypatch.setattr(common, "secretsmanager_client", FakeSecrets())
    return fake_idp_server


def setup_sessions_mocks(monkeypatch):
    """Setup sessions table mocks"""
    import home_app.home as home
    import home_app.sessions as sessions
    import home_app.common as common

    fake_sessions = MockedSessionsTable()
    monkeypatch.setattr(home, "sessions_table", fake_sessions)
    monkeypatch.setattr(sessions, "sessions_table", fake_sessions)
    monkeypatch.setattr(common, "sessions_table", fake_sessions)
    return fake_sessions
