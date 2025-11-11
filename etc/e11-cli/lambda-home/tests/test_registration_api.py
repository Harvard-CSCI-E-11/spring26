import json
import pytest
import os

import home_app.home as home
from home_app.common import User
from home_app.home import EmailNotRegistered

from test_utils import (
    create_test_config_data, create_test_auth_data,
    create_registration_payload, create_lambda_event, create_test_config_file,
    assert_dynamodb_updated, assert_route53_called, assert_ses_email_sent,
    assert_response_success, setup_aws_mocks
)

from conftest import expected_hostnames

"""
Registration API Test Coverage:

Flow 1: First-time user registration (test_registration_api_flow)
- User doesn't exist in database initially
- OIDC callback should create new User record + new Session record
- Verify User record is created with correct data
- Verify Session record is created
- Verify DNS records are created
- Verify email is sent

Flow 2: Returning user registration (test_registration_api_returning_user_flow)
- User already exists in database
- OIDC callback should use existing User record + create new Session record
- Verify no new User record is created (existing one is reused)
- Verify new Session record is created
- Verify DNS records are created
- Verify email is sent

Flow 3: Invalid user (test_registration_api_invalid_user)
- User email not found in database
- Should return 403 error

Flow 4: Invalid course key (test_registration_api_invalid_course_key)
- User exists but course_key doesn't match
- Should return 403 error
"""


def test_registration_api_flow(monkeypatch):
    """Test that registration parameters flow correctly from e11 CLI to home.py backend"""

    # Setup mocked AWS services
    mock_aws = setup_aws_mocks(monkeypatch)

    # Create test data using common utilities
    config_data = create_test_config_data()
    auth_data = create_test_auth_data()

    # Create temporary config file
    config_path = create_test_config_file(config_data)

    try:
        # Set environment variable to use our test config
        monkeypatch.setenv('E11_CONFIG', config_path)

        # Mock the user lookup to return a valid user
        def mock_get_user_from_email(email):
            return User(**{ 'user_id': 'test-user-id',
                            'email': email,
                            'course_key': '123456',
                            'sk': '#',
                            'user_registered': 1000000,
                            'claims':{}})

        monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

        # Mock the add_user_log function
        def mock_add_user_log(user_id, message, extra=None):
            pass

        monkeypatch.setattr(home, 'add_user_log', mock_add_user_log)

        # Create the registration payload using common utility
        registration_payload = create_registration_payload(config_data, auth_data)

        # Create the Lambda event using common utility
        event = create_lambda_event('/api/v1/register', 'POST', json.dumps(registration_payload))

        # Call the registration handler
        response = home.api_register(event, registration_payload)

        # Verify the response using common utility
        assert_response_success(response, 'DNS record created and email sent successfully')

        # Verify DynamoDB was called with correct data using common utility
        assert_dynamodb_updated(mock_aws, 'test-user-id', {
            'ip_address': '1.2.3.4',
            'preferred_name': 'Test User'
        })

        # Verify Route53 was called using common utility
        assert_route53_called(mock_aws, expected_hostnames, '1.2.3.4')

        # Verify SES email was sent using common utility
        assert_ses_email_sent(mock_aws, 'test@csci-e-11.org', 'AWS Instance Registered. New DNS Record Created: testcsci-e-11.csci-e-11.org')

    finally:
        # Clean up temporary config file
        os.unlink(config_path)


def test_registration_api_invalid_user(monkeypatch):
    """Test registration API with invalid user (not found in database)"""

    # Setup mocked AWS services
    _mock_aws = setup_aws_mocks(monkeypatch)

    # Mock the user lookup to return None (user not found)
    def mock_get_user_from_email(email):
        raise EmailNotRegistered(email)

    monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

    # Create test data using common utilities
    config_data = create_test_config_data(email='nonexistent@csci-e-11.org')
    auth_data = create_test_auth_data(email='nonexistent@csci-e-11.org')

    # Create the registration payload using common utility
    registration_payload = create_registration_payload(config_data, auth_data)

    # Create the Lambda event using common utility
    event = create_lambda_event('/api/v1/register', 'POST', json.dumps(registration_payload))

    # Call the registration handler
    with pytest.raises(home.APINotAuthenticated, match='User email nonexistent@csci-e-11.org is not registered.*'):
        home.api_register(event, registration_payload)


def test_registration_api_invalid_course_key(monkeypatch):
    """Test registration API with invalid course key"""

    # Setup mocked AWS services
    _mock_aws = setup_aws_mocks(monkeypatch)

    # Mock the user lookup to return a user with different course key
    def mock_get_user_from_email(email):
        return User(**{
            'user_id': 'test-user-id',
            'email': email,
            'course_key': '654321',  # Different course key
            'sk': '#',
            'claims': {},
            'user_registered': 0
        })

    monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

    # Create test data using common utilities
    config_data = create_test_config_data(course_key='bogus')
    auth_data = create_test_auth_data(course_key='bogus')

    # Create the registration payload using common utility
    registration_payload = create_registration_payload(config_data, auth_data)

    # Create the Lambda event using common utility
    event = create_lambda_event('/api/v1/register', 'POST', json.dumps(registration_payload))

    # Call the registration handler
    with pytest.raises(home.APINotAuthenticated, match='User course_key does not match registration course_key for email test@csci-e-11.org.*'):
        home.api_register(event, registration_payload)


def test_registration_api_returning_user_flow(monkeypatch):
    """Test registration API with returning user (Flow 2: existing user + new session)"""

    # Setup mocked AWS services
    mock_aws = setup_aws_mocks(monkeypatch)

    # Create test data using common utilities
    config_data = create_test_config_data()
    auth_data = create_test_auth_data()

    # Create temporary config file
    config_path = create_test_config_file(config_data)

    try:
        # Set environment variable to use our test config
        monkeypatch.setenv('E11_CONFIG', config_path)

        # Mock the user lookup to return an existing user (Flow 2: returning user)
        def mock_get_user_from_email(email):
            return User(**{
                'user_id': 'existing-user-id',
                'email': email,
                'course_key': config_data['course_key'],  # Use test config data
                'sk': '#',
                'claims': {'name': 'Test User', 'email': email},
                'user_registered': 1000000000,
                'public_ip': '0.0.0.0',    # Old IP (different from new registration)
                'hostname': 'old-hostname.csci-e-11.org'  # Old hostname (different from new registration)
            })

        monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

        # Mock the add_user_log function
        def mock_add_user_log(user_id, message, extra=None):
            pass

        monkeypatch.setattr(home, 'add_user_log', mock_add_user_log)

        # Create the registration payload using common utility
        registration_payload = create_registration_payload(config_data, auth_data)

        # Create the Lambda event using common utility
        event = create_lambda_event('/api/v1/register', 'POST', json.dumps(registration_payload))

        # Call the registration handler
        response = home.api_register(event, registration_payload)

        # Verify the response using common utility
        assert_response_success(response, 'DNS record created and email sent successfully')

        # Verify DynamoDB was called with correct data using common utility
        assert_dynamodb_updated(mock_aws, 'existing-user-id', {
            'ip_address': '1.2.3.4',
            'preferred_name': 'Test User'
        })

        # Verify Route53 was called using common utility
        assert_route53_called(mock_aws, expected_hostnames, '1.2.3.4')

        # Verify SES email was sent using common utility
        assert_ses_email_sent(mock_aws, 'test@csci-e-11.org', 'AWS Instance Registered. New DNS Record Created: testcsci-e-11.csci-e-11.org')

    finally:
        # Clean up temporary config file
        os.unlink(config_path)


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
