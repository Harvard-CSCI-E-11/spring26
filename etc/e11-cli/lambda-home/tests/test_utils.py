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

from e11.e11_common import DNS_TTL

logger = logging.getLogger()


class MockedAWSServices:
    """
    Consolidated AWS services tracker for testing registration API.
    
    NOTE: This class is used ONLY for tracking Route53 and SES calls.
    We use DynamoDB Local for testing, NOT mocking. DynamoDB operations
    should use the real DynamoDB Local tables via the `fake_aws` fixture.
    """

    def __init__(self):
        self.route53_changes = []
        self.ses_emails = []    # list of sent mails
        self.secrets = {}


# Test Data Factories
def create_test_config_data(**overrides) -> Dict[str, Any]:
    """Create standardized test configuration data"""
    from e11.e11core.constants import COURSE_DOMAIN
    default_data = {
        'preferred_name': 'Test User',
        'email': f'test@{COURSE_DOMAIN}',
        'course_key': '123456',
        'public_ip': '1.2.3.4',
        'instanceId': 'i-1234567890abcdef0'
    }
    default_data.update(overrides)
    return default_data


def create_test_auth_data(**overrides) -> Dict[str, Any]:
    """Create standardized test authentication data"""
    from e11.e11core.constants import COURSE_DOMAIN
    default_data = {
        'email': f'test@{COURSE_DOMAIN}',
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
def assert_route53_called(mock_aws: MockedAWSServices, expected_hostnames: List[str], expected_ip: str = '1.2.3.4'):
    """Assert that Route53 was called with expected hostnames"""
    assert len(mock_aws.route53_changes) == 1, f"Expected 1 Route53 call, got {len(mock_aws.route53_changes)}"

    route53_change = mock_aws.route53_changes[0]
    from e11.e11_common import HOSTED_ZONE_ID
    assert route53_change['HostedZoneId'] == HOSTED_ZONE_ID

    changes = route53_change['ChangeBatch']['Changes']
    if len(changes) != len(expected_hostnames):
        logger.error("changes=%s",json.dumps(changes,indent=4,default=str))
        logger.error("expected_hostnames=%s",json.dumps(expected_hostnames,indent=4,default=str))
    assert len(changes) == len(expected_hostnames), f"Expected {len(expected_hostnames)} DNS changes, got {len(changes)}"

    for change in changes:
        assert change['Action'] == 'UPSERT'
        assert change['ResourceRecordSet']['Type'] == 'A'
        assert change['ResourceRecordSet']['TTL'] == DNS_TTL
        assert change['ResourceRecordSet']['ResourceRecords'][0]['Value'] == expected_ip
        assert change['ResourceRecordSet']['Name'] in expected_hostnames


def assert_ses_email_sent(mock_aws: MockedAWSServices, expected_recipient: str, expected_subject_contains: Optional[str] = None):
    """Assert that SES email was sent with expected recipient"""
    from e11.e11_common import SES_VERIFIED_EMAIL
    for msg in mock_aws.ses_emails:
        if msg['Source'] == SES_VERIFIED_EMAIL:
            subject_match = True
            if expected_subject_contains:
                subject_match = expected_subject_contains in msg['Message']['Subject']['Data']
            if subject_match and expected_recipient in msg['Destination']['ToAddresses']:
                return

    error_msg = f"Could not find email with recipient '{expected_recipient}'"
    if expected_subject_contains:
        error_msg += f" and subject containing '{expected_subject_contains}'"
    error_msg += f" in ses_emails: {json.dumps(mock_aws.ses_emails, indent=4, default=str)}"
    logger.error(error_msg)
    raise AssertionError(error_msg)


def assert_response_success(response: Dict[str, Any], expected_message_contains: Optional[str] = None):
    """Assert that API response indicates success"""
    assert response['statusCode'] == 200, f"Expected status 200, got {response['statusCode']}"

    if expected_message_contains:
        response_body = json.loads(response['body'])
        assert expected_message_contains in response_body['message']


def assert_response_error(response: Dict[str, Any], expected_status: int, expected_message_contains: Optional[str] = None):
    """Assert that API response indicates an error"""
    assert response['statusCode'] == expected_status, f"Expected status {expected_status}, got {response['statusCode']}"

    if expected_message_contains:
        response_body = json.loads(response['body'])
        assert expected_message_contains in response_body.get('message', '')


# Environment Setup Helpers
def setup_oidc_mocks(monkeypatch, fake_idp_server):
    """Setup OIDC-specific mocks"""
    import e11.e11_common as e11_common

    class FakeSecrets:
        def get_secret_value(self, SecretId):
            return {"SecretString": json.dumps({
                "oidc_discovery_endpoint": fake_idp_server["discovery"],
                "client_id": "client-123",
                "redirect_uri": "https://app.example.org/auth/callback",
                "hmac_secret": "super-secret-hmac",
                "secret_key": "client-secret-xyz",
            })}

    monkeypatch.setattr(e11_common, "secretsmanager_client", FakeSecrets())
    return fake_idp_server
