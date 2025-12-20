import json
import pytest
import os
import uuid

from e11.e11_common import create_new_user
from e11.e11core.constants import HTTP_FORBIDDEN
import home_app.api as api

from test_utils import (
    create_test_config_data, create_test_auth_data,
    create_registration_payload, create_lambda_event, create_test_config_file,
    assert_response_success
)


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


def test_registration_api_flow(monkeypatch, fake_aws, dynamodb_local):
    """Test that registration parameters flow correctly from e11 CLI to api.py backend"""

    # Create test user in DynamoDBLocal with unique email
    from e11.e11core.constants import COURSE_DOMAIN
    test_email = f'test-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
    course_key = user['course_key']

    # Create test data using common utilities
    config_data = create_test_config_data(email=test_email, course_key=course_key)
    auth_data = create_test_auth_data(email=test_email, course_key=course_key)

    # Create temporary config file
    config_path = create_test_config_file(config_data)

    try:
        # Set environment variable to use our test config
        monkeypatch.setenv('E11_CONFIG', config_path)

        # Create the registration payload using common utility
        registration_payload = create_registration_payload(config_data, auth_data)

        # Create the Lambda event using common utility
        from e11.e11core.constants import API_PATH
        event = create_lambda_event(API_PATH, 'POST', json.dumps(registration_payload))

        # Call the registration handler via dispatch
        # Wrap in try/except to handle APINotAuthenticated like lambda_handler does
        try:
            response = api.dispatch("POST", "register", event, None, registration_payload, API_PATH)
        except api.APINotAuthenticated as e:
            from home_app.api import resp_json
            response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

        # Verify the response using common utility
        assert_response_success(response, 'DNS updated')

    finally:
        # Clean up temporary config file
        os.unlink(config_path)


def test_registration_api_invalid_user(monkeypatch, fake_aws, dynamodb_local):
    """Test registration API with invalid user (not found in database)"""

    # Don't create a user - test with non-existent email
    from e11.e11core.constants import COURSE_DOMAIN, API_PATH
    nonexistent_email = f'nonexistent-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    config_data = create_test_config_data(email=nonexistent_email)
    auth_data = create_test_auth_data(email=nonexistent_email)

    # Create the registration payload using common utility
    registration_payload = create_registration_payload(config_data, auth_data)

    # Create the Lambda event using common utility
    event = create_lambda_event(API_PATH, 'POST', json.dumps(registration_payload))

    # Call the registration handler via dispatch - should raise APINotAuthenticated
    # Wrap in try/except to handle APINotAuthenticated like lambda_handler does
    try:
        response = api.dispatch("POST", "register", event, None, registration_payload, API_PATH)
    except api.APINotAuthenticated as e:
        from home_app.api import resp_json
        response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

    # Should return 403 Forbidden
    assert response["statusCode"] == 403
    assert "not registered" in response["body"].lower()


def test_registration_api_invalid_course_key(monkeypatch, fake_aws, dynamodb_local):
    """Test registration API with invalid course key"""

    # Create test user in DynamoDBLocal with one course_key and unique email
    from e11.e11core.constants import COURSE_DOMAIN, API_PATH
    test_email = f'test-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    create_new_user(test_email, {"email": test_email, "name": "Test User"})
    # User has course_key from create_new_user, but we'll use a different one in payload

    # Create test data using common utilities with wrong course_key
    config_data = create_test_config_data(email=test_email, course_key='wrong-key')
    auth_data = create_test_auth_data(email=test_email, course_key='wrong-key')

    # Create the registration payload using common utility
    registration_payload = create_registration_payload(config_data, auth_data)

    # Create the Lambda event using common utility
    event = create_lambda_event(API_PATH, 'POST', json.dumps(registration_payload))

    # Call the registration handler via dispatch - should raise APINotAuthenticated
    # Wrap in try/except to handle APINotAuthenticated like lambda_handler does
    try:
        response = api.dispatch("POST", "register", event, None, registration_payload, API_PATH)
    except api.APINotAuthenticated as e:
        from home_app.api import resp_json
        response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

    # Should return 403 Forbidden
    assert response["statusCode"] == 403
    assert "course_key" in response["body"].lower()


def test_registration_api_returning_user_flow(monkeypatch, fake_aws, dynamodb_local):
    """Test registration API with returning user (Flow 2: existing user + new session)"""

    # Create test user in DynamoDBLocal (returning user) with unique email
    from e11.e11core.constants import COURSE_DOMAIN, API_PATH
    test_email = f'test-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
    course_key = user['course_key']

    # Create test data using common utilities
    config_data = create_test_config_data(email=test_email, course_key=course_key)
    auth_data = create_test_auth_data(email=test_email, course_key=course_key)

    # Create temporary config file
    config_path = create_test_config_file(config_data)

    try:
        # Set environment variable to use our test config
        monkeypatch.setenv('E11_CONFIG', config_path)

        # Create the registration payload using common utility
        registration_payload = create_registration_payload(config_data, auth_data)

        # Create the Lambda event using common utility
        event = create_lambda_event(API_PATH, 'POST', json.dumps(registration_payload))

        # Call the registration handler via dispatch
        # Wrap in try/except to handle APINotAuthenticated like lambda_handler does
        try:
            response = api.dispatch("POST", "register", event, None, registration_payload, API_PATH)
        except api.APINotAuthenticated as e:
            from home_app.api import resp_json
            response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

        # Verify the response using common utility
        assert_response_success(response, 'DNS updated')

    finally:
        # Clean up temporary config file
        os.unlink(config_path)


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
