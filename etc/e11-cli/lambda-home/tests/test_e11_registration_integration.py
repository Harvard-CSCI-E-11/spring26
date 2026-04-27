import json as json_module
import pytest
from unittest.mock import Mock, patch

from e11.e11_common import create_new_user
import home_app.api as api


from test_utils import ( create_test_config_data, create_test_config_file )


def test_e11_registration_with_test_config(monkeypatch, fake_aws, dynamodb_local, clean_dynamodb):
    """Test e11 registration command using the test config file"""

    # Create test user in DynamoDB Local
    import uuid
    from e11.e11core.constants import COURSE_DOMAIN
    test_email = f'user-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
    course_key = user['course_key']

    # Create test config data using common utilities instead of external file
    test_config_data = create_test_config_data(
        preferred_name='Test User',
        email=test_email,
        course_key=course_key,
        public_ip='1.2.3.4'
    )

    # Mock the requests.post to capture what e11 CLI would send
    captured_requests = []

    def mock_requests_post(url, json=None, **kwargs):
        captured_requests.append({
            'url': url,
            'json': json,
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
                'body': json_module.dumps(json),
                'isBase64Encoded': False
            }

            response = api.dispatch("POST", "register", event, None, json)
            return Mock(
                ok=response['statusCode'] == 200,
                text=response['body'],
                status_code=response['statusCode'],
                json=lambda: json
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

    def mock_get_instance_id():
        return 'i-1234567890abcdef0'

    config_path = create_test_config_file(test_config_data)
    monkeypatch.setenv('E11_CONFIG', config_path)

    import e11.main as e11_main
    monkeypatch.setattr(e11_main, 'get_instanceId', mock_get_instance_id)
    monkeypatch.setattr(e11_main, 'get_public_ip', lambda: test_config_data['public_ip'])

    args = Mock(quiet=True, stage=False, fixip=False, source="test")
    with patch('e11.main.requests.post', side_effect=mock_requests_post), \
         patch('e11.main.requests.get', side_effect=mock_requests_get), \
         patch('subprocess.run', side_effect=mock_subprocess_run):
        e11_main.do_register(args)

    assert len(captured_requests) == 1
    request = captured_requests[0]
    from e11.e11core.constants import API_ENDPOINT
    assert request['url'] == API_ENDPOINT

    registration_data = request['json']['registration']
    assert registration_data['preferred_name'] == test_config_data['preferred_name']
    assert registration_data['email'] == test_config_data['email']
    assert registration_data['course_key'] == test_config_data['course_key']
    assert registration_data['public_ip'] == test_config_data['public_ip']


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
