"""
SQS support for lambda-home.

SQS is used to queue grading for bulk-grading and for lab7 and lab8, where grading is initiated by interactions with the leaderboard or the dashboard.

SQS Message Authentication:
Messages sent to SQS should include an 'auth_token' field in the message body that is an HMAC signature
of the message content (using itsdangerous.Signer with SHA1). The secret key is stored in AWS Secrets Manager
under the key specified by SQS_AUTH_SECRET_ID environment variable.

To send an authenticated message:
1. Get the shared secret from Secrets Manager
2. Create a canonical representation of the message (action + method + payload JSON)
3. Use itsdangerous.Signer(secret_key=secret).sign(canonical_message) to create the signature
4. Include the signed value (base64-encoded) as 'auth_token' in the message body

Alternatively, you can rely on AWS IAM policies to restrict who can send messages to the queue,
which provides authentication at the infrastructure level. However, HMAC provides an additional
layer of validation that the message content hasn't been tampered with.
"""

import functools
import json
import os
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError
from itsdangerous import Signer, BadSignature

from e11.e11core.utils import get_logger
from e11.e11_common import sqs_client, secretsmanager_client

from . import api

LOGGER = get_logger("home")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
SQS_QUEUE_ARN = os.environ.get("SQS_QUEUE_ARN", "")
SQS_AUTH_SECRET_ID = os.environ.get("SQS_SECRET_ID", "")


@functools.lru_cache(maxsize=1)
def _get_sqs_auth_secret() -> Optional[str]:
    """
    Get the shared secret for SQS message authentication from Secrets Manager.
    Returns None if SQS_AUTH_SECRET_ID is not configured (authentication disabled).
    Results are cached to avoid repeated Secrets Manager calls.
    """
    if not SQS_AUTH_SECRET_ID:
        LOGGER.error("SQS_AUTH_SECRET_ID not provided")
        return None
    try:
        secret_response = secretsmanager_client.get_secret_value(SecretId=SQS_AUTH_SECRET_ID)
        secret_string = secret_response.get("SecretString", "")
        # The secret might be stored as JSON or as a plain string
        try:
            secret_dict = json.loads(secret_string)
            # Try common key names
            secret = secret_dict.get("sqs_auth_secret") or secret_dict.get("auth_secret") or secret_dict.get("secret")
        except json.JSONDecodeError:
            # Plain string
            secret = secret_string

        if not secret:
            LOGGER.warning("SQS auth secret found but empty in Secrets Manager")
            return None
        return secret
    except (ClientError, json.JSONDecodeError, KeyError) as e:
        LOGGER.error("Failed to get SQS auth secret from Secrets Manager: %s", e)
        return None


def sign_sqs_message(action: str, method: str, payload: Optional[Dict[str, Any]] = None) -> str:
    """
    Create a signed SQS message body with authentication token.

    Args:
        action: The API action to dispatch
        method: The HTTP method (typically 'POST')
        payload: Optional payload data

    Returns:
        JSON string of the message body with auth_token included

    The message will be signed using the secret from Secrets Manager if configured.
    If no secret is configured, the message will be sent without authentication.
    """
    # Create canonical representation: action + method + sorted JSON of payload
    if payload is None:
        payload_str = "null"
    else:
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))

    canonical_message = f"{action}:{method}:{payload_str}"

    # Build the message body
    message_body: Dict[str, Any] = {
        "action": action,
        "method": method,
        "payload": payload,
    }

    # Sign the message if authentication is enabled
    secret = _get_sqs_auth_secret()
    if secret:
        signer = Signer(secret_key=secret, salt="sqs-auth-v1")
        auth_token = signer.sign(canonical_message)
        # Signer.sign() returns bytes, decode to string for JSON serialization
        message_body["auth_token"] = auth_token.decode('utf-8') if isinstance(auth_token, bytes) else auth_token
        LOGGER.debug("SQS message signed for action=%s method=%s", action, method)
    else:
        LOGGER.debug("SQS message not signed (authentication disabled) for action=%s method=%s", action, method)
        raise RuntimeError("Could not get sqs_auth_secret")

    return json.dumps(message_body)


def validate_sqs_message_auth(body: Dict[str, Any]) -> bool:
    """
    Validate the authentication token in an SQS message.

    Args:
        body: The parsed JSON message body containing 'action', 'method', 'payload', and 'auth_token'

    Returns:
        True if authentication is valid or disabled, False if authentication fails

    Authentication is disabled (returns True) if:
    - SQS_AUTH_SECRET_ID is not configured
    - The secret cannot be retrieved from Secrets Manager

    Authentication fails (returns False) if:
    - 'auth_token' is missing and authentication is enabled
    - The computed HMAC doesn't match the provided 'auth_token'
    """
    secret = _get_sqs_auth_secret()

    # If no secret is configured, authentication is disabled
    if secret is None:
        LOGGER.debug("SQS message authentication disabled (no secret configured)")
        return True

    # Get the auth token from the message
    provided_token = body.get("auth_token")
    if not provided_token:
        LOGGER.warning("SQS message missing auth_token but authentication is enabled")
        return False

    # Create canonical representation: action + method + sorted JSON of payload
    action = body.get("action", "")
    method = body.get("method", "POST")
    payload = body.get("payload")

    # Create a deterministic JSON representation of the payload
    if payload is None:
        payload_str = "null"
    else:
        payload_str = json.dumps(payload, sort_keys=True, separators=(',', ':'))

    canonical_message = f"{action}:{method}:{payload_str}"

    # Use itsdangerous.Signer to validate the signature
    # Signer uses HMAC-SHA1 by default, which is secure for HMAC (unlike for signatures)
    # The auth_token should be the result of signer.sign(canonical_message), which includes
    # the message + signature. We unsign it to verify and extract the message.
    signer = Signer(secret_key=secret, salt="sqs-auth-v1")
    try:
        # This will raise BadSignature if the signature doesn't match
        # unsign() returns the original message (bytes), so we decode and compare
        unsigned_message = signer.unsign(provided_token).decode('utf-8')
        if unsigned_message != canonical_message:
            LOGGER.warning("SQS message canonical content mismatch")
            return False
        # If we get here, the signature is valid and the message matches
        LOGGER.debug("SQS message authentication successful")
        return True
    except BadSignature:
        LOGGER.warning("SQS message auth_token validation failed")
        return False

def sqs_send_message(message_body: str, *, delay_seconds: int = 0,
                     message_attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Send one message to the stack-owned queue.

    Args:
        message_body: JSON string of the message body (can be created with sign_sqs_message())
        delay_seconds: Optional delay before message becomes visible
        message_attributes: Optional SQS message attributes

    Returns:
        boto3's response (includes MessageId).
    """
    if not SQS_QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL is not set")

    kwargs: Dict[str, Any] = {
        "QueueUrl": SQS_QUEUE_URL,
        "MessageBody": message_body,
    }
    if delay_seconds:
        kwargs["DelaySeconds"] = int(delay_seconds)
    if message_attributes:
        # boto3 expects the SQS wire format for attributes.
        kwargs["MessageAttributes"] = message_attributes

    result = sqs_client.send_message(**kwargs)
    return result  # type: ignore[return-value]


def sqs_send_signed_message(action: str, method: str, payload: Optional[Dict[str, Any]] = None,
                           *, delay_seconds: int = 0,
                           message_attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Send a signed SQS message to the queue.

    This is a convenience function that signs the message and sends it.

    Args:
        action: The API action to dispatch
        method: The HTTP method (typically 'POST')
        payload: Optional payload data
        delay_seconds: Optional delay before message becomes visible
        message_attributes: Optional SQS message attributes

    Returns:
        boto3's response (includes MessageId).
    """
    signed_body = sign_sqs_message(action, method, payload)
    return sqs_send_message(signed_body, delay_seconds=delay_seconds, message_attributes=message_attributes)


def sqs_receive_one(*, wait_seconds: int = 10, visibility_timeout: int = 60,
                    validate_auth: bool = True) -> Optional[Dict[str, Any]]:
    """
    Long-poll for up to wait_seconds and return ONE message (or None).

    Args:
        wait_seconds: How long to wait for a message
        visibility_timeout: How long message is hidden after receipt
        validate_auth: If True, validate the message authentication token

    Returns:
        SQS message dict (with 'body', 'messageId', etc.) or None if no message received.
        If validate_auth=True and validation fails, raises ValueError.
    """
    if not SQS_QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL is not set")

    resp = sqs_client.receive_message(
        QueueUrl=SQS_QUEUE_URL,
        MaxNumberOfMessages=1,
        WaitTimeSeconds=int(wait_seconds),
        VisibilityTimeout=int(visibility_timeout),
        AttributeNames=["All"],
        MessageAttributeNames=["All"],
    )
    msgs = resp.get("Messages") or []
    if not msgs:
        return None

    msg = msgs[0]  # type: ignore[assignment]

    # Validate authentication if requested
    if validate_auth:
        try:
            body = json.loads(msg.get("body", ""))
            if not validate_sqs_message_auth(body):
                LOGGER.error("SQS messageId=%s: Authentication validation failed", msg.get("messageId"))
                raise ValueError("SQS message authentication failed")
        except json.JSONDecodeError as e:
            LOGGER.error("SQS messageId=%s: Invalid JSON in body: %s", msg.get("messageId"), e)
            raise ValueError("Invalid JSON in SQS message body") from e

    return msg  # type: ignore[return-value]


def sqs_delete_message(receipt_handle: str) -> None:
    """
    Delete a message after successful processing.
    """
    if not SQS_QUEUE_URL:
        raise RuntimeError("SQS_QUEUE_URL is not set")

    sqs_client.delete_message(
        QueueUrl=SQS_QUEUE_URL,
        ReceiptHandle=receipt_handle,
    )

def is_sqs_event(event: Dict[str, Any]) -> bool:
    recs = event.get("Records")
    return (
        isinstance(recs, list)
        and len(recs) > 0
        and recs[0].get("eventSource") == "aws:sqs"
    )


# pylint: disable=unused-argument
def handle_sqs_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS-triggered deliveries.
    Note: with an SQS event source mapping, messages are deleted automatically
    if your handler completes successfully (no exception).

    Each SQS message body should be JSON containing:
    - 'action': the API action to dispatch
    - 'method': the HTTP method (typically 'POST')
    - 'payload': optional payload data (if None, will be set to None)
    - 'auth_token': optional authentication token for SQS message validation
    """
    results = []
    for record in event.get("Records", []):
        msg_id = record.get("messageId")
        body_str = record.get("body", "")
        LOGGER.info("SQS messageId=%s body_len=%s", msg_id, len(body_str))

        try:
            # Parse the message body
            body = json.loads(body_str) if body_str else {}
            action = body.get("action", "")
            method = body.get("method", "POST")
            payload = body.get("payload")  # Can be None

            # Authenticate the SQS message
            if not validate_sqs_message_auth(body):
                LOGGER.error("SQS messageId=%s: Authentication failed", msg_id)
                raise ValueError("SQS message authentication failed")

            # Create a minimal event structure for api.dispatch
            # SQS events don't have requestContext, so we create a minimal one
            sqs_event = {
                "requestContext": {
                    "stage": "sqs",
                    "http": {
                        "method": method,
                        "sourceIp": record.get("attributes", {}).get("SenderId", "sqs-internal")
                    }
                },
                "source": "sqs",
                "messageId": msg_id,
                "receiptHandle": record.get("receiptHandle"),
            }

            # Call api.dispatch with the action and method from the message
            result = api.dispatch(method, action, sqs_event, context, payload)
            results.append({"messageId": msg_id, "result": result})

        except json.JSONDecodeError as e:
            LOGGER.error("SQS messageId=%s: Invalid JSON in body: %s", msg_id, e)
            # Re-raise to make message visible again after VisibilityTimeout
            raise
        except Exception as e:
            LOGGER.exception("SQS messageId=%s: Error processing message: %s", msg_id, e)
            # Re-raise to make message visible again after VisibilityTimeout
            raise

    return {"ok": True, "processed": len(results), "results": results}
