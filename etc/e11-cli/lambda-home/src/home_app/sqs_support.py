"""
SQS support for lambda-home.

SQS is used to queue grading for bulk-grading and for lab7 and lab8, where grading is initiated by interactions with the leaderboard or the dashboard.
"""

import os
from typing import Any, Dict, Optional

from e11.e11core.utils import get_logger
from e11.e11_common import sqs_client

LOGGER = get_logger("home")
SQS_QUEUE_URL = os.environ.get("SQS_QUEUE_URL", "")
SQS_QUEUE_ARN = os.environ.get("SQS_QUEUE_ARN", "")

def sqs_send_message(message_body: str, *, delay_seconds: int = 0,
                     message_attributes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Send one message to the stack-owned queue.
    Returns boto3's response (includes MessageId).
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


def sqs_receive_one(*, wait_seconds: int = 10, visibility_timeout: int = 60) -> Optional[Dict[str, Any]]:
    """
    Long-poll for up to wait_seconds and return ONE message (or None).
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
    return msgs[0] if msgs else None  # type: ignore[return-value]


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


# pylint: disable=unused-argument,fixme
def handle_sqs_event(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    Process SQS-triggered deliveries.
    Note: with an SQS event source mapping, messages are deleted automatically
    if your handler completes successfully (no exception).
    """
    for record in event.get("Records", []):
        msg_id = record.get("messageId")
        body = record.get("body", "")
        LOGGER.info("SQS messageId=%s body_len=%s", msg_id, len(body))

        # TODO: your real processing here
        # If you raise, the message will become visible again after VisibilityTimeout.

    return {"ok": True}
