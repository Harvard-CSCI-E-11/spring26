import json
import pytest
import os
import subprocess
import tempfile
import configparser
from unittest.mock import Mock, patch, MagicMock
import requests
import sys

import home_app.home as home
import home_app.common as common
from home_app.common import User

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
                    for attr_name, attr_value in ExpressionAttributeValues.items():
                        if attr_name == ':ip':
                            item['ip_address'] = attr_value
                        elif attr_name == ':hn':
                            item['hostname'] = attr_value
                        elif attr_name == ':t':
                            item['host_registered'] = attr_value
                        elif attr_name == ':name':
                            item['name'] = attr_value
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
        monkeypatch.setattr(common, 'secretsmanager_client', MockSecretsManager(self))

        # Set environment variables
        monkeypatch.setenv('OIDC_SECRET_ID', 'fake-secret-id')
        monkeypatch.setenv('DDB_REGION', 'us-east-1')
        monkeypatch.setenv('DDB_USERS_TABLE_ARN', 'arn:aws:dynamodb:us-east-1:000000000000:table/fake-users-table')
        monkeypatch.setenv('SESSIONS_TABLE_NAME', 'fake-sessions-table')
        monkeypatch.setenv('COOKIE_DOMAIN', 'csci-e-11.org')
        monkeypatch.setenv('HOSTED_ZONE_ID', 'Z05034072HOMXYCK23BRA')


def test_e11_registration_with_test_config(monkeypatch):
    """Test e11 registration command using the test config file"""

    # Setup mocked AWS services
    mock_aws = MockedAWSServices()
    mock_aws.setup_mocks(monkeypatch)

    # Get the path to the test config file
    test_config_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),  # Go up to workspace root
        'tests', 'data', 'e11-config-test.ini'
    )

    # Verify the test config file exists
    assert os.path.exists(test_config_path), f"Test config file not found: {test_config_path}"

    # Read the test config to get expected values
    config = configparser.ConfigParser()
    config.read(test_config_path)
    test_config_data = dict(config['student'])

    # Mock the user lookup to return a valid user
    def mock_get_user_from_email(email):
        return User(**{
            'user_id': 'test-user-id',
            'email': email,
            'course_key': test_config_data['course_key'],
            'user_registered': 1000000,
            'sk': '#'
        })

    monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

    # Mock the add_user_log function
    def mock_add_user_log(user_id, message, extra=None):
        # Just a no-op for testing
        pass

    monkeypatch.setattr(home, 'add_user_log', mock_add_user_log)

    # Mock the requests.post to capture what e11 CLI would send
    captured_requests = []

    def mock_requests_post(url, json_data=None, **kwargs):
        captured_requests.append({
            'url': url,
            'json': json_data,
            'kwargs': kwargs
        })

        # Simulate the registration API response
        if url == 'https://csci-e-11.org/api/v1/register':
            # Call the actual registration handler with the captured data
            event = {
                'rawPath': '/api/v1/register',
                'requestContext': {
                    'http': {
                        'method': 'POST',
                        'sourceIp': test_config_data.get('public_ip', '1.2.3.4')
                    }
                },
                'body': json.dumps(json_data),
                'isBase64Encoded': False
            }

            response = home.api_register(event, json_data)
            return Mock(
                ok=response['statusCode'] == 200,
                text=response['body'],
                status_code=response['statusCode']
            )

        return Mock(ok=False, text="Not found", status_code=404)

    # Mock the requests.get for IP address check
    def mock_requests_get(url, **kwargs):
        if 'checkip.amazonaws.com' in url:
            return Mock(text=test_config_data.get('public_ip', '1.2.3.4'))
        return Mock(text="Not found")

            # Mock subprocess for EC2 instance ID check
        def mock_subprocess_run(cmd, **kwargs):
            if 'dmidecode' in cmd:
                return Mock(stdout='ec2-12345678-1234-1234-1234-123456789012')
            elif '169.254.169.254' in ' '.join(cmd):
                return Mock(text='i-1234567890abcdef0')
            return Mock(stdout='', stderr='', returncode=0)

        # Mock the get_instanceId function
        def mock_get_instance_id():
            return 'i-1234567890abcdef0'

            # Apply the mocks
        with patch('requests.post', side_effect=mock_requests_post), \
             patch('requests.get', side_effect=mock_requests_get), \
             patch('subprocess.run', side_effect=mock_subprocess_run):

            # Set environment variable to use our test config
            monkeypatch.setenv('E11_CONFIG', test_config_path)

            # Mock EC2 check to return True
            def mock_on_ec2():
                return True

            # Import and patch the e11 module
            import e11.__main__ as e11_main
            monkeypatch.setattr(e11_main, 'on_ec2', mock_on_ec2)
            monkeypatch.setattr(e11_main, 'get_instanceId', mock_get_instance_id)

        # Call the registration function directly
        args = Mock()
        e11_main.api_register(args)

        # Verify that a request was made to the registration endpoint
        assert len(captured_requests) == 1
        request = captured_requests[0]
        assert request['url'] == 'https://csci-e-11.org/api/v1/register'

        # Verify the registration payload contains the config data
        registration_data = request['json']['registration']
        assert registration_data['name'] == test_config_data['name']
        assert registration_data['email'] == test_config_data['email']
        assert registration_data['course_key'] == test_config_data['course_key']
        assert registration_data['public_ip'] == test_config_data['public_ip']

        # Verify the backend processed the registration correctly
        assert len(mock_aws.dynamodb_items) > 0

        # Find the user update
        user_update_found = False
        for key, item in mock_aws.dynamodb_items.items():
            if key[0] == 'test-user-id' and key[1] == '#':
                assert item.get('ip_address') == test_config_data['public_ip']
                assert item.get('name') == test_config_data['name']
                assert 'host_registered' in item
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
            'user.csci-e-11.org',  # Based on email user@csci-e-11.org
            'user-lab1.csci-e-11.org',
            'user-lab2.csci-e-11.org',
            'user-lab3.csci-e-11.org',
            'user-lab4.csci-e-11.org',
            'user-lab5.csci-e-11.org',
            'user-lab6.csci-e-11.org',
            'user-lab7.csci-e-11.org'
        ]

        assert len(changes) == len(expected_hostnames)
        for change in changes:
            assert change['Action'] == 'UPSERT'
            assert change['ResourceRecordSet']['Type'] == 'A'
            assert change['ResourceRecordSet']['TTL'] == 300
            assert change['ResourceRecordSet']['ResourceRecords'][0]['Value'] == test_config_data['public_ip']
            assert change['ResourceRecordSet']['Name'] in expected_hostnames

        # Verify SES email was sent
        assert len(mock_aws.ses_emails) == 1
        ses_email = mock_aws.ses_emails[0]
        assert ses_email['Source'] == 'admin@csci-e-11.org'
        assert ses_email['Destination']['ToAddresses'] == [test_config_data['email']]

        # Verify email content
        message = ses_email['Message']
        assert 'AWS Instance Registered' in message['Subject']['Data']

        email_body = message['Body']['Text']['Data']
        assert test_config_data['public_ip'] in email_body  # IP address
        assert test_config_data['course_key'] in email_body  # course key
        assert 'user.csci-e-11.org' in email_body  # hostname


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
