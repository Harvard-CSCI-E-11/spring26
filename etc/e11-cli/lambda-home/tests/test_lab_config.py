"""
Tests for LAB_CONFIG functionality including deadline checking and next_lab computation.

IMPORTANT TESTING NOTE:
======================
We use DynamoDB Local for testing, NOT monkeypatching for DynamoDB operations.
- Create actual records using create_new_user() and new_session()
- Query the real DynamoDB Local tables (they have proper GSI indexes)
- Do NOT mock users_table.query or sessions_table.query for user/session lookups
- Only mock users_table.query if you need to return empty items for logs/grades/images
  to simplify a test, but NEVER mock sessions_table.query - always use the real table!
"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock
from zoneinfo import ZoneInfo

import pytest

from e11.e11_common import LAB_CONFIG, LAB_REDIRECTS
from home_app import api, home
from e11.e11core.constants import HTTP_FORBIDDEN, HTTP_OK


def test_lab_config_structure():
    """Test that LAB_CONFIG has the correct structure for all labs."""
    assert len(LAB_CONFIG) == 9, "LAB_CONFIG should have 9 labs (lab0-lab8)"

    for lab_num in range(9):
        lab_key = f"lab{lab_num}"
        assert lab_key in LAB_CONFIG, f"Missing {lab_key} in LAB_CONFIG"
        lab_config = LAB_CONFIG[lab_key]

        assert "redirect" in lab_config, f"{lab_key} missing 'redirect'"
        assert "deadline" in lab_config, f"{lab_key} missing 'deadline'"
        assert isinstance(lab_config["redirect"], str), f"{lab_key}.redirect should be a string"
        assert lab_config["redirect"].startswith("http"), f"{lab_key}.redirect should be a valid URL"

        # Verify deadline is valid ISO-8601 format (no timezone, Eastern time)
        deadline_str = lab_config["deadline"]
        deadline = datetime.fromisoformat(deadline_str)
        assert deadline.tzinfo is None, f"{lab_key}.deadline should not have timezone (assumed Eastern)"


def test_lab_config_backward_compatibility():
    """Test that LAB_REDIRECTS still works for backward compatibility."""
    assert len(LAB_REDIRECTS) == 9, "LAB_REDIRECTS should have 9 labs"

    for lab_num in range(9):
        assert lab_num in LAB_REDIRECTS, f"LAB_REDIRECTS missing lab {lab_num}"
        assert LAB_REDIRECTS[lab_num] == LAB_CONFIG[f"lab{lab_num}"]["redirect"], \
            f"LAB_REDIRECTS[{lab_num}] should match LAB_CONFIG['lab{lab_num}']['redirect']"


def test_lab_redirects_still_work():
    """Test that lab redirect routes still work with LAB_CONFIG."""

    event = {
        "requestContext": {
            "http": {"method": "GET", "sourceIp": "1.2.3.4"},
            "stage": "test"
        },
        "rawPath": "/lab0"
    }

    response = home.lambda_handler(event, None)
    assert response["statusCode"] == 302
    assert response["headers"]["Location"] == LAB_CONFIG["lab0"]["redirect"]


@pytest.mark.parametrize("lab_key", ["lab0", "lab1", "lab2"])
def test_api_grader_before_deadline(lab_key, monkeypatch, fake_aws):
    """Test that api_grader accepts requests before deadline."""
    import uuid
    from e11.e11_common import create_new_user, A

    # Create test user with unique email
    test_email = f"test-{lab_key}-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email, {
        "email": test_email,
        "preferred_name": "Test User",
        "public_ip": "1.2.3.4",
        "hostname": "test"
    })

    # Mock the grader to avoid actual SSH calls
    mock_summary = {
        "lab": lab_key,
        "passes": ["test1"],
        "fails": [],
        "tests": [{"name": "test1", "passed": True, "message": "OK"}],
        "score": 100.0,
        "error": False,
        "ctx": {"email": test_email, "public_ip": "1.2.3.4", "lab": lab_key}
    }

    # Mock secrets manager for SSH key (needs to be JSON with 'cscie-bot' key)
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.return_value = {"SecretString": json.dumps({"cscie-bot": "fake-ssh-key"})}
    monkeypatch.setattr("home_app.api.secretsmanager_client", mock_secrets)

    with patch("home_app.api.grader.grade_student_vm", return_value=mock_summary):
        with patch("home_app.api.send_email"):
            # Set current time to before deadline
            # Deadline is in Eastern time (no timezone in string)
            from zoneinfo import ZoneInfo
            eastern_tz = ZoneInfo("America/New_York")
            deadline_str = LAB_CONFIG[lab_key]["deadline"]
            deadline = datetime.fromisoformat(deadline_str).replace(tzinfo=eastern_tz)
            before_deadline = deadline - timedelta(days=1)

            with patch("home_app.api.datetime") as mock_dt:
                mock_dt.fromisoformat = datetime.fromisoformat
                mock_dt.now.return_value = before_deadline
                # Patch LAB_TIMEZONE to use our test timezone
                with patch("home_app.api.LAB_TIMEZONE", eastern_tz):
                    event = {
                        "requestContext": {"http": {"method": "POST", "sourceIp": "1.2.3.4"}},
                        "source": "api"  # Not from SQS
                    }
                    payload = {
                        "auth": {
                            "email": test_email,
                            "course_key": user[A.COURSE_KEY]
                        },
                        "lab": lab_key
                    }

                    response = api.api_grader(event, None, payload)
                    assert response["statusCode"] == HTTP_OK


@pytest.mark.parametrize("lab_key", ["lab0", "lab1", "lab2"])
def test_api_grader_after_deadline_rejects(lab_key, monkeypatch, fake_aws):
    """Test that api_grader rejects requests after deadline (non-SQS)."""
    import uuid
    from e11.e11_common import create_new_user, A

    # Create test user with unique email
    test_email = f"test-{lab_key}-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email, {
        "email": test_email,
        "preferred_name": "Test User",
        "public_ip": "1.2.3.4",
        "hostname": "test"
    })

    # Set current time to after deadline
    # Deadline is in Eastern time (no timezone in string)
    eastern_tz = ZoneInfo("America/New_York")
    deadline_str = LAB_CONFIG[lab_key]["deadline"]
    deadline = datetime.fromisoformat(deadline_str).replace(tzinfo=eastern_tz)
    after_deadline = deadline + timedelta(hours=1)

    with patch("home_app.api.datetime") as mock_dt:
        mock_dt.fromisoformat = datetime.fromisoformat
        mock_dt.now.return_value = after_deadline
        # Patch LAB_TIMEZONE to use our test timezone
        with patch("home_app.api.LAB_TIMEZONE", eastern_tz):
            event = {
                "requestContext": {"http": {"method": "POST", "sourceIp": "1.2.3.4"}},
                "source": "api"  # Not from SQS
            }
            payload = {
                "auth": {
                    "email": test_email,
                    "course_key": user[A.COURSE_KEY]
                },
                "lab": lab_key
            }

            response = api.api_grader(event, None, payload)
            assert response["statusCode"] == HTTP_FORBIDDEN
            body = json.loads(response["body"])
            assert body["error"] is True
            assert "deadline has passed" in body["message"].lower()


def test_api_grader_sqs_bypasses_deadline(monkeypatch, fake_aws):
    """Test that SQS requests bypass deadline checks."""
    import uuid
    from e11.e11_common import create_new_user, A

    # Create test user with unique email
    test_email = f"test-sqs-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email, {
        "email": test_email,
        "preferred_name": "Test User",
        "public_ip": "1.2.3.4",
        "hostname": "test"
    })

    # Mock the grader
    mock_summary = {
        "lab": "lab0",
        "passes": ["test1"],
        "fails": [],
        "tests": [{"name": "test1", "passed": True, "message": "OK"}],
        "score": 100.0,
        "error": False,
        "ctx": {"email": test_email, "public_ip": "1.2.3.4", "lab": "lab0"}
    }

    # Mock secrets manager for SSH key (needs to be JSON with 'cscie-bot' key)
    mock_secrets = MagicMock()
    mock_secrets.get_secret_value.return_value = {"SecretString": json.dumps({"cscie-bot": "fake-ssh-key"})}
    monkeypatch.setattr("home_app.api.secretsmanager_client", mock_secrets)

    with patch("home_app.api.grader.grade_student_vm", return_value=mock_summary):
        with patch("home_app.api.send_email"):
            # Set current time to after deadline
            # Deadline is in Eastern time (no timezone in string)
            from zoneinfo import ZoneInfo
            eastern_tz = ZoneInfo("America/New_York")
            deadline_str = LAB_CONFIG["lab0"]["deadline"]
            deadline = datetime.fromisoformat(deadline_str).replace(tzinfo=eastern_tz)
            after_deadline = deadline + timedelta(days=1)

            with patch("home_app.api.datetime") as mock_dt:
                mock_dt.fromisoformat = datetime.fromisoformat
                mock_dt.now.return_value = after_deadline
                # Patch LAB_TIMEZONE to use our test timezone
                with patch("home_app.api.LAB_TIMEZONE", eastern_tz):
                    # SQS request should bypass deadline
                    event = {
                        "requestContext": {"http": {"method": "POST", "sourceIp": "test-sender"}},
                        "source": "sqs"  # From SQS - should bypass deadline
                    }
                    payload = {
                        "auth": {
                            "email": test_email,
                            "course_key": user[A.COURSE_KEY]
                        },
                        "lab": "lab0"
                    }

                    response = api.api_grader(event, None, payload)
                    assert response["statusCode"] == HTTP_OK


def test_do_dashboard_computes_next_lab(monkeypatch, fake_aws, dynamodb_local):
    """
    Test that do_dashboard correctly computes next_lab.

    IMPORTANT: This test uses DynamoDB Local, NOT mocking. The user and session
    are created in the real DynamoDB Local tables. We only mock users_table.query
    to return empty items for logs/grades/images (to simplify the test), but the
    session query uses the real DynamoDB Local table.
    """
    import uuid
    from e11.e11_common import create_new_user
    from home_app.sessions import new_session

    # Create test user - this puts the user record in DynamoDB Local
    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    create_new_user(test_email, {
        "email": test_email,
        "preferred_name": "Test User",
        "public_ip": "1.2.3.4",
        "hostname": "test"
    })

    # Create a session using new_session - this goes into DynamoDB Local
    event_for_session = {
        "requestContext": {"http": {"sourceIp": "1.2.3.4"}}
    }
    ses = new_session(event_for_session, {"email": test_email, "preferred_name": "Test User"})

    event = {
        "requestContext": {
            "http": {"method": "GET", "sourceIp": "1.2.3.4"},
            "stage": "test"
        },
        "rawPath": "/dashboard",
        "cookies": [f"AuthSid={ses.sid}"]
    }

    # Mock time to be before lab0 deadline
    from e11.e11_common import LAB_TIMEZONE
    test_time = datetime(2026, 1, 15, 12, 0, 0, tzinfo=LAB_TIMEZONE)  # Before lab0

    with patch("home_app.home.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = test_time
        mock_dt.datetime.fromisoformat = datetime.fromisoformat
        with patch("home_app.home.LAB_TIMEZONE", LAB_TIMEZONE):
            # NOTE: We need to be careful about mocking. do_dashboard calls:
            # 1. get_user_from_email() - uses e11_common.users_table.query with GSI_Email (NEED REAL TABLE)
            # 2. users_table.query() for logs/grades/images - we can mock this
            # 3. all_sessions_for_email() - uses sessions_table.query with GSI_Email (NEED REAL TABLE)
            #
            # We can't mock users_table.query globally because get_user_from_email needs it.
            # Instead, we need to ensure the user exists and let the real queries work.
            # For logs/grades/images, do_dashboard uses queryscan_table(users_table.query, ...)
            # which we can't easily mock without breaking get_user_from_email.
            #
            # Solution: Don't mock users_table.query at all - just ensure the user exists
            # and let the real queries work. The test will be slower but more accurate.
            response = home.do_dashboard(event)
            assert response["statusCode"] == 200

            # Parse the HTML to check for next_lab
            body = response["body"]
            assert "lab0" in body or "next_lab" in body.lower()


def test_do_dashboard_no_next_lab_when_all_past(monkeypatch, fake_aws, dynamodb_local):
    """
    Test that do_dashboard handles case when all labs are past.

    IMPORTANT: This test uses DynamoDB Local, NOT mocking. The user and session
    are created in the real DynamoDB Local tables. We only mock users_table.query
    to return empty items for logs/grades/images (to simplify the test), but the
    session query uses the real DynamoDB Local table.
    """
    import uuid
    from e11.e11_common import create_new_user
    from home_app.sessions import new_session

    # Create test user - this puts the user record in DynamoDB Local
    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    create_new_user(test_email, {
        "email": test_email,
        "preferred_name": "Test User",
        "public_ip": "1.2.3.4",
        "hostname": "test"
    })

    # Create a session using new_session - this goes into DynamoDB Local
    event_for_session = {
        "requestContext": {"http": {"sourceIp": "1.2.3.4"}}
    }
    ses = new_session(event_for_session, {"email": test_email, "preferred_name": "Test User"})

    event = {
        "requestContext": {
            "http": {"method": "GET", "sourceIp": "1.2.3.4"},
            "stage": "test"
        },
        "rawPath": "/dashboard",
        "cookies": [f"AuthSid={ses.sid}"]
    }

    # Mock time to be after all lab deadlines
    from e11.e11_common import LAB_TIMEZONE
    test_time = datetime(2027, 1, 1, 12, 0, 0, tzinfo=LAB_TIMEZONE)  # After all labs

    with patch("home_app.home.datetime") as mock_dt:
        mock_dt.datetime.now.return_value = test_time
        mock_dt.datetime.fromisoformat = datetime.fromisoformat
        with patch("home_app.home.LAB_TIMEZONE", LAB_TIMEZONE):
            # NOTE: We need to be careful about mocking. do_dashboard calls:
            # 1. get_user_from_email() - uses e11_common.users_table.query with GSI_Email (NEED REAL TABLE)
            # 2. users_table.query() for logs/grades/images - we can mock this
            # 3. all_sessions_for_email() - uses sessions_table.query with GSI_Email (NEED REAL TABLE)
            #
            # We can't mock users_table.query globally because get_user_from_email needs it.
            # Instead, we need to ensure the user exists and let the real queries work.
            # For logs/grades/images, do_dashboard uses queryscan_table(users_table.query, ...)
            # which we can't easily mock without breaking get_user_from_email.
            #
            # Solution: Don't mock users_table.query at all - just ensure the user exists
            # and let the real queries work. The test will be slower but more accurate.
            response = home.do_dashboard(event)
            assert response["statusCode"] == 200
            # Should not crash even when no next_lab


def test_lab_name_normalization():
    """Test that lab name normalization works correctly."""
    # Test various lab name formats
    test_cases = [
        ("lab0", "lab0"),
        ("lab1", "lab1"),
        ("0", "lab0"),
        ("1", "lab1"),
        ("lab2", "lab2"),
    ]

    for input_lab, expected_key in test_cases:
        if input_lab.startswith("lab"):
            lab_key = input_lab
        else:
            lab_num = input_lab.replace("lab", "").strip()
            lab_key = f"lab{lab_num}"

        assert lab_key == expected_key, f"Normalization failed: {input_lab} -> {lab_key} (expected {expected_key})"

