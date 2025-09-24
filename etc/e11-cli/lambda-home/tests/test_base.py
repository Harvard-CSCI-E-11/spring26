"""
Base test classes for common test patterns.
This module provides specialized base classes for different types of tests.
"""

import pytest
from typing import Dict, Any, List, Optional
from test_utils import MockedAWSServices, MockedSessionsTable, setup_aws_mocks, setup_oidc_mocks, setup_sessions_mocks


class BaseAWSTest:
    """Base class for tests requiring AWS service mocking"""

    @pytest.fixture(autouse=True)
    def setup_aws_services(self, monkeypatch):
        """Setup AWS mocks for all tests in this class"""
        self.mock_aws = setup_aws_mocks(monkeypatch)
        yield self.mock_aws


class BaseOIDCTest:
    """Base class for OIDC flow tests"""

    @pytest.fixture(autouse=True)
    def setup_oidc_services(self, monkeypatch, fake_idp_server):
        """Setup OIDC-specific mocks for all tests in this class"""
        self.fake_idp_server = setup_oidc_mocks(monkeypatch, fake_idp_server)
        yield self.fake_idp_server


class BaseAPITest:
    """Base class for API endpoint tests"""

    @pytest.fixture(autouse=True)
    def setup_api_services(self, monkeypatch):
        """Setup API-specific mocks for all tests in this class"""
        self.mock_aws = setup_aws_mocks(monkeypatch)
        self.mock_sessions = setup_sessions_mocks(monkeypatch)
        yield {
            'aws': self.mock_aws,
            'sessions': self.mock_sessions
        }


class BaseRegistrationTest(BaseAWSTest):
    """Base class specifically for registration API tests"""

    @pytest.fixture(autouse=True)
    def setup_registration_services(self, monkeypatch):
        """Setup registration-specific mocks"""
        # Call parent setup
        super().setup_aws_services(monkeypatch)

        # Additional registration-specific setup
        import home_app.home as home
        from home_app.common import User

        # Mock the user lookup function
        def mock_get_user_from_email(email):
            return User(**{
                'user_id': 'test-user-id',
                'email': email,
                'course_key': '123456',
                'sk': '#',
                'user_registered': 1000000,
                'claims': {}
            })

        monkeypatch.setattr(home, 'get_user_from_email', mock_get_user_from_email)

        # Mock the add_user_log function
        def mock_add_user_log(user_id, message, extra=None):
            pass

        monkeypatch.setattr(home, 'add_user_log', mock_add_user_log)

        yield self.mock_aws


class BaseIntegrationTest(BaseAWSTest):
    """Base class for integration tests that test the full flow"""

    @pytest.fixture(autouse=True)
    def setup_integration_services(self, monkeypatch):
        """Setup integration test mocks"""
        # Call parent setup
        super().setup_aws_services(monkeypatch)

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

        # Mock EC2 check to return True
        def mock_on_ec2():
            return True

        # Apply the mocks
        with patch('subprocess.run', side_effect=mock_subprocess_run):
            # Import and patch the e11 module
            import e11.__main__ as e11_main
            monkeypatch.setattr(e11_main, 'on_ec2', mock_on_ec2)
            monkeypatch.setattr(e11_main, 'get_instanceId', mock_get_instance_id)

        yield self.mock_aws


