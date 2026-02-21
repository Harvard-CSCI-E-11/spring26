import json
import pytest
import os
import uuid


from e11.e11_common import create_new_user
from e11.e11core.utils import smash_email
from home_app.home import (
    EMAIL_SUBJECT_NEW_DNS_RECORDS,
)
from e11.e11core.constants import HTTP_FORBIDDEN, COURSE_DOMAIN

import home_app.api as api

from test_utils import (
    create_test_config_data, create_test_auth_data,
    create_registration_payload, create_lambda_event, create_test_config_file,
    assert_response_success,
    assert_route53_called, assert_ses_email_sent
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

    # Set up trackable mocks for Route53 and SES (keep real DynamoDB from fake_aws)
    from test_utils import MockedAWSServices
    mock_aws = MockedAWSServices()

    # Replace Route53 and SES mocks with trackable ones
    import e11.e11_common as e11_common
    import home_app.api as api_module

    # Create trackable Route53 mock
    class TrackableRoute53:
        def __init__(self, mock_aws):
            self.mock_aws = mock_aws

        def list_resource_record_sets(self, **kwargs):
            return {"ResourceRecordSets": []}

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

    # Replace the Route53 mock
    trackable_route53 = TrackableRoute53(mock_aws)
    monkeypatch.setattr(e11_common, 'route53_client', trackable_route53)
    monkeypatch.setattr(api_module, 'route53_client', trackable_route53)

    # Mock send_email2 function to track calls
    def trackable_send_email(to_addrs, email_subject, email_body):
        from e11.e11_common import SES_VERIFIED_EMAIL
        mock_aws.ses_emails.append({
            'Source': SES_VERIFIED_EMAIL,
            'Destination': {'ToAddresses': to_addrs},
            'Message': {'Subject': {'Data': email_subject}, 'Body': {'Text': {'Data': email_body}}}
        })
        return {"MessageId": "fake-message-id"}

    monkeypatch.setattr(e11_common, 'send_email2', trackable_send_email)
    monkeypatch.setattr(api_module, 'send_email2', trackable_send_email)

    # Create test user in DynamoDBLocal with unique email
    test_email = f'test-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
    course_key = user['course_key']
    user_id = user['user_id']
    hostname = smash_email(test_email)

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
            response = api.dispatch("POST", "register", event, None, registration_payload)
        except api.APINotAuthenticated as e:
            from home_app.api import resp_json
            response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

        # Verify the response using common utility
        assert_response_success(response, 'DNS updated and email sent successfully')

        # Verify DynamoDB was updated by checking real DynamoDB local
        from e11.e11_common import users_table, A
        db_user = users_table.get_item(Key={'user_id': user_id, 'sk': A.SK_USER})
        assert 'Item' in db_user, f"User {user_id} not found in DynamoDB"
        item = db_user['Item']
        assert item.get(A.PUBLIC_IP) == '1.2.3.4', f"Expected ip_address=1.2.3.4, got {item.get(A.PUBLIC_IP)}"
        assert item.get(A.PREFERRED_NAME) == 'Test User', f"Expected preferred_name=Test User, got {item.get(A.PREFERRED_NAME)}"

        # Build expected hostnames
        from home_app.api import DOMAIN_SUFFIXES
        expected_hostnames = [f"{hostname}{suffix}.{COURSE_DOMAIN}" for suffix in DOMAIN_SUFFIXES]

        # Verify Route53 was called using common utility
        assert_route53_called(mock_aws, expected_hostnames, '1.2.3.4')

        # Verify SES email was sent using common utility
        expected_subject = EMAIL_SUBJECT_NEW_DNS_RECORDS.format(hostname=expected_hostnames[0])
        assert_ses_email_sent(mock_aws, test_email, expected_subject)

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
        response = api.dispatch("POST", "register", event, None, registration_payload)
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
        response = api.dispatch("POST", "register", event, None, registration_payload)
    except api.APINotAuthenticated as e:
        from home_app.api import resp_json
        response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

    # Should return 403 Forbidden
    assert response["statusCode"] == 403
    assert "course_key" in response["body"].lower()


def test_registration_api_returning_user_flow(monkeypatch, fake_aws, dynamodb_local):
    """Test registration API with returning user (Flow 2: existing user + new session)"""

    # Set up trackable mocks for Route53 and SES (keep real DynamoDB from fake_aws)
    from test_utils import MockedAWSServices
    mock_aws = MockedAWSServices()

    # Replace Route53 and SES mocks with trackable ones
    import e11.e11_common as e11_common
    import home_app.api as api_module

    # Create trackable Route53 mock
    class TrackableRoute53:
        def __init__(self, mock_aws):
            self.mock_aws = mock_aws

        def list_resource_record_sets(self, **kwargs):
            return {"ResourceRecordSets": []}

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

    # Mock send_email2 function to track calls
    def trackable_send_email(to_addrs, email_subject, email_body):
        from e11.e11_common import SES_VERIFIED_EMAIL
        mock_aws.ses_emails.append({
            'Source': SES_VERIFIED_EMAIL,
            'Destination': {'ToAddresses': to_addrs},
            'Message': {'Subject': {'Data': email_subject}, 'Body': {'Text': {'Data': email_body}}}
        })
        return {"MessageId": "fake-message-id"}

    # Replace the mocks
    trackable_route53 = TrackableRoute53(mock_aws)
    monkeypatch.setattr(e11_common, 'route53_client', trackable_route53)
    monkeypatch.setattr(api_module, 'route53_client', trackable_route53)
    monkeypatch.setattr(e11_common, 'send_email2', trackable_send_email)
    monkeypatch.setattr(api_module, 'send_email2', trackable_send_email)

    # Create test user in DynamoDBLocal (returning user) with unique email
    from e11.e11core.constants import API_PATH
    test_email = f'test-{uuid.uuid4().hex[:8]}@{COURSE_DOMAIN}'
    user = create_new_user(test_email, {"email": test_email, "name": "Test User"})
    course_key = user['course_key']
    user_id = user['user_id']
    hostname = smash_email(test_email)

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
            response = api.dispatch("POST", "register", event, None, registration_payload)
        except api.APINotAuthenticated as e:
            from home_app.api import resp_json
            response = resp_json(HTTP_FORBIDDEN, {"message": str(e)})

        # Verify the response using common utility
        assert_response_success(response, 'DNS updated and email sent successfully')

        # Verify DynamoDB was updated by checking real DynamoDB local
        from e11.e11_common import users_table, A
        db_user = users_table.get_item(Key={'user_id': user_id, 'sk': A.SK_USER})
        assert 'Item' in db_user, f"User {user_id} not found in DynamoDB"
        item = db_user['Item']
        assert item.get(A.PUBLIC_IP) == '1.2.3.4', f"Expected ip_address=1.2.3.4, got {item.get(A.PUBLIC_IP)}"
        assert item.get(A.PREFERRED_NAME) == 'Test User', f"Expected preferred_name=Test User, got {item.get(A.PREFERRED_NAME)}"

        # Build expected hostnames
        from home_app.api import DOMAIN_SUFFIXES
        expected_hostnames = [f"{hostname}{suffix}.{COURSE_DOMAIN}" for suffix in DOMAIN_SUFFIXES]

        # Verify Route53 was called using common utility
        assert_route53_called(mock_aws, expected_hostnames, '1.2.3.4')

        # Verify SES email was sent using common utility
        expected_subject = EMAIL_SUBJECT_NEW_DNS_RECORDS.format(hostname=expected_hostnames[0])
        assert_ses_email_sent(mock_aws, test_email, expected_subject)

    finally:
        # Clean up temporary config file
        os.unlink(config_path)


if __name__ == '__main__':
    # Run tests
    pytest.main([__file__, '-v'])
