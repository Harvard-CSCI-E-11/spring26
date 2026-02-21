"""
Test for queue_grade function and SQS message processing.
"""

import json
import uuid
from unittest.mock import MagicMock

import pytest

from e11.e11_common import A, create_new_user
from home_app import home, sqs_support


class MockSQSClient:
    """Mock SQS client that stores messages in memory."""

    def __init__(self):
        self.messages = []  # List of messages sent
        self.message_counter = 0

    def send_message(self, QueueUrl, MessageBody, **kwargs):
        """Store the message and return a response."""
        self.message_counter += 1
        message_id = f"test-msg-{self.message_counter}"
        self.messages.append({
            "MessageId": message_id,
            "Body": MessageBody,
            "QueueUrl": QueueUrl,
            **kwargs
        })
        return {
            "MessageId": message_id,
            "ResponseMetadata": {"HTTPStatusCode": 200}
        }

    def receive_message(self, **kwargs):
        """Return a stored message if available."""
        if self.messages:
            msg = self.messages.pop(0)
            return {
                "Messages": [{
                    "MessageId": msg["MessageId"],
                    "Body": msg["Body"],
                    "ReceiptHandle": f"receipt-{msg['MessageId']}",
                    "Attributes": {"SenderId": "test-sender"}
                }]
            }
        return {"Messages": []}


class MockSecretsManager:
    """Mock Secrets Manager that returns test secrets."""

    def __init__(self, secret_value="foobar"):
        self.secret_value = secret_value

    def get_secret_value(self, SecretId):
        """Return the test secret."""
        return {"SecretString": self.secret_value}


class MockGrader:
    """Mock grader that returns test results."""

    @staticmethod
    def grade_student_vm(email, public_ip, lab, pkey_pem=None, key_filename=None):
        """Return a mock grading summary."""
        return {
            "lab": lab,
            "passes": ["test1", "test2"],
            "fails": [],
            "tests": [
                {"name": "test1", "passed": True, "message": "OK"},
                {"name": "test2", "passed": True, "message": "OK"}
            ],
            "score": 100.0,
            "error": False,
            "ctx": {
                "email": email,
                "public_ip": public_ip,
                "lab": lab
            }
        }

    @staticmethod
    def create_email(summary, note=None):
        """Return mock email subject and body."""
        return (
            f"Grading Results for {summary['lab']}",
            f"Your score: {summary['score']}"
        )


@pytest.fixture
def mock_sqs(monkeypatch):
    """Set up mock SQS client."""
    mock_sqs_client = MockSQSClient()
    import e11.e11_common as e11_common
    monkeypatch.setattr(e11_common, "sqs_client", mock_sqs_client)
    monkeypatch.setattr(sqs_support, "sqs_client", mock_sqs_client)
    return mock_sqs_client


@pytest.fixture
def mock_secrets_manager(monkeypatch):
    """Set up mock Secrets Manager."""
    mock_secrets = MockSecretsManager("foobar")
    import e11.e11_common as e11_common
    monkeypatch.setattr(e11_common, "secretsmanager_client", mock_secrets)
    monkeypatch.setattr(sqs_support, "secretsmanager_client", mock_secrets)
    monkeypatch.setenv("SQS_SECRET_ID", "test-sqs-secret-id")
    monkeypatch.setenv("SQS_QUEUE_URL", "https://sqs.us-east-1.amazonaws.com/123456789/test-queue")
    monkeypatch.setenv("SQS_QUEUE_ARN", "arn:aws:sqs:us-east-1:123456789:test-queue")
    # Also need to update the module-level variables
    import importlib
    importlib.reload(sqs_support)
    return mock_secrets


@pytest.fixture
def mock_grader(monkeypatch):
    """Set up mock grader."""
    from e11.e11core import grader
    monkeypatch.setattr(grader, "grade_student_vm", MockGrader.grade_student_vm)
    monkeypatch.setattr(grader, "create_email", MockGrader.create_email)
    return MockGrader()


@pytest.fixture
def test_user(fake_aws, dynamodb_local):
    """Create a test user in DynamoDB."""
    import time
    from e11.e11core.utils import smash_email
    from e11.e11_common import users_table

    test_email = f"test-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email, {
        "email": test_email,
        "preferred_name": "Test User",
    })
    # Register the instance by setting public_ip on the user record
    users_table.update_item(
        Key={"user_id": user[A.USER_ID], "sk": user[A.SK]},
        UpdateExpression=f"SET {A.PUBLIC_IP} = :ip, {A.HOSTNAME} = :hn, {A.HOST_REGISTERED} = :t",
        ExpressionAttributeValues={
            ":ip": "1.2.3.4",
            ":hn": smash_email(test_email),
            ":t": int(time.time()),
        }
    )
    # create_new_user generates a course_key, so we need to use the one it created
    return {"email": test_email, "course_key": user["course_key"]}


@pytest.fixture
def mock_ses(monkeypatch):
    """Set up mock SES client."""
    sent_emails = []

    class MockSESClient:
        def send_email(self, Source, Destination, Message):
            sent_emails.append({
                "Source": Source,
                "Destination": Destination,
                "Message": Message
            })
            return {"MessageId": "test-email-id"}

    mock_ses_client = MockSESClient()
    import e11.e11_common as e11_common
    monkeypatch.setattr(e11_common, "ses_client", mock_ses_client)
    monkeypatch.setattr(home, "ses_client", mock_ses_client)

    return sent_emails


def test_queue_grade_sends_message(mock_sqs, mock_secrets_manager, test_user, fake_aws):
    """Test that queue_grade sends a properly formatted SQS message."""
    # Call queue_grade
    result = home.queue_grade(test_user["email"], "lab0", note='test')

    # Verify message was sent
    assert len(mock_sqs.messages) == 1
    assert result["MessageId"] == mock_sqs.messages[0]["MessageId"]

    # Parse the message body
    message_body = json.loads(mock_sqs.messages[0]["Body"])

    # Verify message structure
    assert message_body["action"] == "grade"
    assert message_body["method"] == "POST"
    assert message_body["payload"]["lab"] == "lab0"
    assert message_body["payload"]["auth"][A.EMAIL] == test_user["email"]
    assert message_body["payload"]["auth"][A.COURSE_KEY] == test_user["course_key"]
    assert "auth_token" in message_body  # Should be signed


def test_queue_grade_handles_sqs_event(mock_sqs, mock_secrets_manager, test_user,
                                       mock_grader, mock_ses, fake_aws, monkeypatch, dynamodb_local):
    """Test the full flow: queue_grade -> handle_sqs_event -> email sent."""
    # Mock the get_pkey_pem function
    def mock_get_pkey_pem(key_name):
        return "fake-ssh-key-pem"

    import home_app.api as api_module
    monkeypatch.setattr(api_module, "get_pkey_pem", mock_get_pkey_pem)

    # Mock add_user_log and add_grade to avoid DynamoDB calls
    def mock_add_user_log(event, user_id, message, **extra):
        pass

    def mock_add_grade(user, lab, public_ip, summary):
        pass

    import e11.e11_common as e11_common

    # Reload the module to pick up the mocked functions
    monkeypatch.setattr(e11_common, "add_user_log", mock_add_user_log)
    monkeypatch.setattr(e11_common, "add_grade", mock_add_grade)

    # Mock send_email2 - it's imported from e11_common in api.py
    def mock_send_email_api(to_addrs, email_subject, email_body):
        mock_ses.append({
            "Source": "noreply@example.com",
            "Destination": {"ToAddresses": to_addrs},
            "Message": {
                "Subject": {"Data": email_subject},
                "Body": {"Text": {"Data": email_body}}
            }
        })

    # Mock it in both places since api.py imports it
    monkeypatch.setattr(e11_common, "send_email2", mock_send_email_api)
    monkeypatch.setattr(api_module, "send_email2", mock_send_email_api)

    # Call queue_grade to send the message
    result = home.queue_grade(test_user["email"], "lab0", note='test')
    assert len(mock_sqs.messages) == 1

    # Repackage the message as an SQS event (as Lambda would receive it)
    sqs_event = {
        "Records": [{
            "messageId": result["MessageId"],
            "body": mock_sqs.messages[0]["Body"],
            "receiptHandle": f"receipt-{result['MessageId']}",
            "attributes": {
                "SenderId": "test-sender"
            },
            "eventSource": "aws:sqs"
        }]
    }

    # Create a mock context
    context = MagicMock()
    context.function_name = "test-function"
    context.function_version = "1"
    context.invoked_function_arn = "arn:aws:lambda:us-east-1:123456789:function:test"

    # Process the SQS event
    response = home.handle_sqs_event(sqs_event, context)

    # Verify the response
    assert response["ok"] is True
    assert response["processed"] == 1

    # Verify email was sent
    assert len(mock_ses) == 1
    email = mock_ses[0]
    assert test_user["email"] in email["Destination"]["ToAddresses"]
    assert "lab0" in email["Message"]["Subject"]["Data"].lower() or "grading" in email["Message"]["Subject"]["Data"].lower()
