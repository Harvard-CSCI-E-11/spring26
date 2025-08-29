import json
import pytest
import os
import tempfile
import configparser
from unittest.mock import Mock, patch, MagicMock

import home_app.home as home

class MockedAWSServices:
    """Mock AWS services for testing registration API"""

    def __init__(self):
        self.dynamodb_items = {}
        self.route53_changes = []
        self.ses_emails = []
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
                    # This is a simplified version - in real implementation you'd parse the expression
                    for attr_name, attr_value in ExpressionAttributeValues.items():
                        if attr_name == ':ip':
                            item['ip_address'] = attr_value
                        elif attr_name == ':hn':
                            item['hostname'] = attr_value
                        elif attr_name == ':t':
                            item['reg_time'] = attr_value
                        elif attr_name == ':name':
                            item['name'] = attr_value
                else:
                    # Create a new item if it doesn't exist
                    item = {
                        'user_id': Key.get('user_id'),
                        'sk': Key.get('sk', '#'),
                        'ip_address': ExpressionAttributeValues.get(':ip'),
                        'hostname': ExpressionAttributeValues.get(':hn'),
                        'reg_time': ExpressionAttributeValues.get(':t'),
                        'name': ExpressionAttributeValues.get(':name')
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
        monkeypatch.setattr(home, 'users_table', MockDynamoDBTable(self))
        monkeypatch.setattr(home, 'route53_client', MockRoute53(self))
        monkeypatch.setattr(home, 'ses_client', MockSES(self))
        monkeypatch.setattr(home, 'secretsmanager_client', MockSecretsManager(self))

        # Set environment variables
        monkeypatch.setenv('OIDC_SECRET_ID', 'fake-secret-id')
        monkeypatch.setenv('DDB_REGION', 'us-east-1')
        monkeypatch.setenv('DDB_USERS_TABLE_ARN', 'arn:aws:dynamodb:us-east-1:000000000000:table/fake-users-table')
        monkeypatch.setenv('SESSIONS_TABLE_NAME', 'fake-sessions-table')
        monkeypatch.setenv('COOKIE_DOMAIN', 'csci-e-11.org')
        monkeypatch.setenv('HOSTED_ZONE_ID', 'Z05034072HOMXYCK23BRA')


def create_test_config(config_data):
    """Create a temporary config file with test data"""
    config = configparser.ConfigParser()
    config['student'] = config_data

    # Create temporary file
    fd, path = tempfile.mkstemp(suffix='.ini')
    os.close(fd)

    with open(path, 'w') as f:
        config.write(f)

    return path


def test_registration_api_flow(monkeypatch):
    """Test that registration parameters flow correctly from e11 CLI to home.py backend"""

    # Setup mocked AWS services
    mock_aws = MockedAWSServices()
    mock_aws.setup_mocks(monkeypatch)

    # Create test config data
    test_config_data = {
        'name': 'Test User',
        'email': 'test@csci-e-11.org',
        'course_key': '123456',
        'ipaddr': '1.2.3.4',
        'instanceId': 'i-1234567890abcdef0'
    }

    # Create temporary config file
    config_path = create_test_config(test_config_data)

    try:
        # Set environment variable to use our test config
        monkeypatch.setenv('E11_CONFIG', config_path)

        # Mock the user lookup to return a valid user
        def mock_get_user_from_email(email):
            return {
                'user_id': 'test-user-id',
                'email': email,
                'course_key': '123456',
                'sk': '#'
            }

        monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

        # Mock the add_user_log function
        def mock_add_user_log(user_id, message, extra=None):
            # Just a no-op for testing
            pass

        monkeypatch.setattr(home, 'add_user_log', mock_add_user_log)

        # Create the registration payload that would be sent by e11 CLI
        registration_payload = {
            'action': 'register',
            'registration': test_config_data
        }

        # Create the Lambda event
        event = {
            'rawPath': '/api/v1/register',
            'requestContext': {
                'http': {
                    'method': 'POST',
                    'sourceIp': '1.2.3.4'
                }
            },
            'body': json.dumps(registration_payload),
            'isBase64Encoded': False
        }

        # Call the registration handler
        response = home.do_register(registration_payload, event)

        # Verify the response
        assert response['statusCode'] == 200
        response_body = json.loads(response['body'])
        assert 'message' in response_body
        assert 'DNS record created and email sent successfully' in response_body['message']

        # Verify DynamoDB was called with correct data
        assert len(mock_aws.dynamodb_items) > 0

        # Find the user update
        user_update_found = False
        for key, item in mock_aws.dynamodb_items.items():
            if key[0] == 'test-user-id' and key[1] == '#':
                assert item.get('ip_address') == '1.2.3.4'
                assert item.get('name') == 'Test User'
                assert 'reg_time' in item
                user_update_found = True
                break

        assert user_update_found, "User record was not updated in DynamoDB"

        # Verify Route53 was called
        assert len(mock_aws.route53_changes) == 1
        route53_change = mock_aws.route53_changes[0]
        assert route53_change['HostedZoneId'] == 'Z05034072HOMXYCK23BRA'

        # Verify DNS records were created for all suffixes
        changes = route53_change['ChangeBatch']['Changes']
        expected_hostnames = [
            'testcsci-e-11.csci-e-11.org',
            'testcsci-e-11-lab1.csci-e-11.org',
            'testcsci-e-11-lab2.csci-e-11.org',
            'testcsci-e-11-lab3.csci-e-11.org',
            'testcsci-e-11-lab4.csci-e-11.org',
            'testcsci-e-11-lab5.csci-e-11.org',
            'testcsci-e-11-lab6.csci-e-11.org',
            'testcsci-e-11-lab7.csci-e-11.org'
        ]

        assert len(changes) == len(expected_hostnames)
        for change in changes:
            assert change['Action'] == 'UPSERT'
            assert change['ResourceRecordSet']['Type'] == 'A'
            assert change['ResourceRecordSet']['TTL'] == 300
            assert change['ResourceRecordSet']['ResourceRecords'][0]['Value'] == '1.2.3.4'
            assert change['ResourceRecordSet']['Name'] in expected_hostnames

        # Verify SES email was sent
        assert len(mock_aws.ses_emails) == 1
        ses_email = mock_aws.ses_emails[0]
        assert ses_email['Source'] == 'admin@csci-e-11.org'
        assert ses_email['Destination']['ToAddresses'] == ['test@csci-e-11.org']

        # Verify email content
        message = ses_email['Message']
        assert message['Subject']['Data'] == 'AWS Instance Registered. New DNS Record Created: testcsci-e-11.csci-e-11.org'

        email_body = message['Body']['Text']['Data']
        assert '1.2.3.4' in email_body  # IP address
        assert '123456' in email_body  # course key
        assert 'Hostname: testcsci-e-11.csci-e-11.org' in email_body  # hostname

    finally:
        # Clean up temporary config file
        os.unlink(config_path)


def test_registration_api_invalid_user(monkeypatch):
    """Test registration API with invalid user (not found in database)"""

    # Setup mocked AWS services
    mock_aws = MockedAWSServices()
    mock_aws.setup_mocks(monkeypatch)

    # Mock the user lookup to return None (user not found)
    def mock_get_user_from_email(email):
        return None

    monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

    # Create test config data
    test_config_data = {
        'name': 'Test User',
        'email': 'nonexistent@csci-e-11.org',
        'course_key': '123456',
        'ipaddr': '1.2.3.4',
        'instanceId': 'i-1234567890abcdef0'
    }

    # Create the registration payload
    registration_payload = {
        'action': 'register',
        'registration': test_config_data
    }

    # Create the Lambda event
    event = {
        'rawPath': '/api/v1/register',
        'requestContext': {
            'http': {
                'method': 'POST',
                'sourceIp': '1.2.3.4'
            }
        },
        'body': json.dumps(registration_payload),
        'isBase64Encoded': False
    }

    # Call the registration handler
    response = home.do_register(registration_payload, event)

    # Verify the response indicates user not found
    assert response['statusCode'] == 403
    response_body = json.loads(response['body'])
    assert 'User email not registered' in response_body['message']
    assert response_body['email'] == 'nonexistent@csci-e-11.org'


def test_registration_api_invalid_course_key(monkeypatch):
    """Test registration API with invalid course key"""

    # Setup mocked AWS services
    mock_aws = MockedAWSServices()
    mock_aws.setup_mocks(monkeypatch)

    # Mock the user lookup to return a user with different course key
    def mock_get_user_from_email(email):
        return {
            'user_id': 'test-user-id',
            'email': email,
            'course_key': '654321',  # Different course key
            'sk': '#'
        }

    monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

    # Create test config data
    test_config_data = {
        'name': 'Test User',
        'email': 'test@csci-e-11.org',
        'course_key': '123456',  # Different from user's course key
        'ipaddr': '1.2.3.4',
        'instanceId': 'i-1234567890abcdef0'
    }

    # Create the registration payload
    registration_payload = {
        'action': 'register',
        'registration': test_config_data
    }

    # Create the Lambda event
    event = {
        'rawPath': '/api/v1/register',
        'requestContext': {
            'http': {
                'method': 'POST',
                'sourceIp': '1.2.3.4'
            }
        },
        'body': json.dumps(registration_payload),
        'isBase64Encoded': False
    }

    # Call the registration handler
    response = home.do_register(registration_payload, event)

    # Verify the response indicates invalid course key
    assert response['statusCode'] == 403
    response_body = json.loads(response['body'])
    assert 'course_key does not match' in response_body['message']
    assert response_body['email'] == 'test@csci-e-11.org'


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
