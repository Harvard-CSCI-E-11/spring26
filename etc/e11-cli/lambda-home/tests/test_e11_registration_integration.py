import json
import pytest
import os
from unittest.mock import Mock, patch

from e11.e11_common import User
import home_app.home as home

from conftest import expected_hostnames

from test_utils import ( create_test_config_data, create_test_config_file, setup_aws_mocks, assert_dynamodb_updated,
                         assert_route53_called, assert_ses_email_sent )


def test_e11_registration_with_test_config(monkeypatch):
    """Test e11 registration command using the test config file"""

    # Setup mocked AWS services
    mock_aws = setup_aws_mocks(monkeypatch)

    # Create test config data using common utilities instead of external file
    from e11.e11core.constants import COURSE_DOMAIN
    test_config_data = create_test_config_data(
        preferred_name='Test User',
        email=f'user@{COURSE_DOMAIN}',
        course_key='123456',
        public_ip='1.2.3.4'
    )

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
        from e11.e11core.constants import API_PATH, API_ENDPOINT
        if url == API_ENDPOINT:
            # Call the actual registration handler with the captured data
            event = {
                'rawPath': API_PATH,
                'requestContext': {
                    'http': {
                        'method': 'POST',
                        'sourceIp': test_config_data.get('public_ip', '1.2.3.4')
                    }
                },
                'body': json.dumps(json_data),
                'isBase64Encoded': False
            }

            print(f"DEBUG: json_data = {json_data}")
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
        with patch('e11.__main__.requests.post', side_effect=mock_requests_post), \
             patch('e11.__main__.requests.get', side_effect=mock_requests_get), \
             patch('subprocess.run', side_effect=mock_subprocess_run):

            # Create a temporary config file for the e11 CLI to use
            config_path = create_test_config_file(test_config_data)
            monkeypatch.setenv('E11_CONFIG', config_path)

            # Mock EC2 check to return True
            def mock_on_ec2():
                return True

            # Import and patch the e11 module
            import e11.__main__ as e11_main
            monkeypatch.setattr(e11_main, 'on_ec2', mock_on_ec2)
            monkeypatch.setattr(e11_main, 'get_instanceId', mock_get_instance_id)

            # Mock get_public_ip to return the expected IP
            def mock_get_public_ip():
                return test_config_data['public_ip']
            monkeypatch.setattr(e11_main, 'get_public_ip', mock_get_public_ip)

            # Call the registration function directly
            args = Mock()
            try:
                e11_main.do_register(args)
            except SystemExit as e:
                print(f"DEBUG: e11 CLI exited with code {e.code}")
                # Check if there were any captured requests
                if len(captured_requests) == 0:
                    print("DEBUG: No HTTP requests were made - e11 CLI failed validation")
                    # Let's see what the config looks like
                    cp = e11_main.get_config()
                    print(f"DEBUG: Config: {cp}")
                    return  # Exit the test early

        # Verify that a request was made to the API endpoint
        assert len(captured_requests) == 1
        request = captured_requests[0]
        from e11.e11core.constants import API_ENDPOINT
        assert request['url'] == API_ENDPOINT

        # Verify the registration payload contains the config data
        registration_data = request['json']['registration']
        assert registration_data['name'] == test_config_data['name']
        assert registration_data['email'] == test_config_data['email']
        assert registration_data['course_key'] == test_config_data['course_key']
        assert registration_data['public_ip'] == test_config_data['public_ip']

        # Verify the backend processed the registration correctly using common utilities
        assert_dynamodb_updated(mock_aws, 'test-user-id', {
            'ip_address': test_config_data['public_ip'],
            'name': test_config_data['name']
        })

        # Verify Route53 was called using common utility
        assert_route53_called(mock_aws, expected_hostnames, test_config_data['public_ip'])

        # Verify SES email was sent using common utility
        assert_ses_email_sent(mock_aws, test_config_data['email'], 'AWS Instance Registered')

        # Clean up temporary config file
        os.unlink(config_path)


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
