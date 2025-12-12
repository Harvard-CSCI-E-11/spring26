"""
Common includes for E11 DynamoDB.
Defines datamodel and simple access routines.
Used by both AWS Lambda and by e11 running in E11_STAFF mode (where staff interact directly with DynamoDB table using their AWS credentials.)
"""

import os
import time
import uuid
import json
import copy
from decimal import Decimal
from typing import Any, TYPE_CHECKING
import datetime

from pydantic import BaseModel, ConfigDict, field_validator
import boto3
from boto3.dynamodb.conditions import Key

from e11.e11core.constants import COURSE_KEY_LEN
from e11.e11core.utils import get_logger

if TYPE_CHECKING:
    from mypy_boto3_route53.client import Route53Client
    from mypy_boto3_secretsmanager.client import SecretsManagerClient
    from mypy_boto3_dynamodb.client import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table as DynamoDBTable
else:
    Route53Client = Any            # pylint: disable=invalid-name
    SecretsManagerClient = Any     # pylint: disable=invalid-name
    DynamoDBClient = Any           # pylint: disable=invalid-name
    DynamoDBServiceResource = Any  # pylint: disable=invalid-name
    DynamoDBTable = Any            # pylint: disable=invalid-name

# COURSE_KEY_LEN is imported from e11.e11core.constants


# DynamoDB config
DDB_REGION = os.environ.get("DDB_REGION","us-east-1")
SECRETS_REGION = os.environ.get("SECRETS_REGION","us-east-1")
ROUTE53_REGION = "us-east-1"
USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME","e11-users")
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME","home-app-sessions")

# DynamoDB values:
dynamodb_client : DynamoDBClient = boto3.client("dynamodb", region_name=DDB_REGION)
dynamodb_resource : DynamoDBServiceResource = boto3.resource( 'dynamodb', region_name=DDB_REGION )
users_table : DynamoDBTable   = dynamodb_resource.Table(USERS_TABLE_NAME)
sessions_table: DynamoDBTable = dynamodb_resource.Table(SESSIONS_TABLE_NAME)
route53_client : Route53Client = boto3.client('route53', region_name=ROUTE53_REGION)
secretsmanager_client : SecretsManagerClient = boto3.client("secretsmanager", region_name=SECRETS_REGION)

# Simple Email Service
SES_VERIFIED_EMAIL = "admin@csci-e-11.org"  # Verified SES email address
ses_client = boto3.client("ses")


# Classes

class DatabaseInconsistency(RuntimeError):
    pass

class EmailNotRegistered(RuntimeError):
    pass

class InvalidCookie(RuntimeError):
    pass

# attributes

class A:                        # pylint: disable=too-few-public-methods
    CLAIMS = 'claims'
    COURSE_KEY = 'course_key'
    EMAIL = 'email'
    HOSTNAME = 'hostname'
    HOST_REGISTERED = 'host_registered'
    LAB = 'lab'
    PREFERRED_NAME = 'preferred_name'
    PUBLIC_IP = 'public_ip'           # public IP address
    SCORE = 'score'
    SESSION_CREATED = 'session_created'  # time_t
    SESSION_EXPIRE = 'session_expire'    # time_t
    SK = 'sk'                   # sort key
    SK_GRADE_PREFIX = 'grade#'         # sort key prefix for log entries
    SK_GRADE_PATTERN = SK_GRADE_PREFIX + "{lab}#{now}"
    SK_LOG_PREFIX = 'log#'         # sort key prefix for log entries
    SK_USER = '#'               # sort key for the user record
    USER_ID = 'user_id'
    USER_REGISTERED = 'user_registered'


def convert_dynamodb_value(value: Any) -> Any:
    """Convert DynamoDB values to Python types."""
    if isinstance(value, Decimal):
        # Convert Decimal to int if it's a whole number, otherwise to float
        if value % 1 == 0:
            return int(value)
        return float(value)
    return value

class DictLikeModel(BaseModel):
    def __getitem__(self, key: str):
        return getattr(self, key)

class User(DictLikeModel):
    """e11-users table sk='#' record"""
    user_id: str
    sk: str
    email: str
    course_key: str
    user_registered: int
    preferred_name: str|None = None
    claims: dict[str, Any] | None = None
    public_ip: str|None = None
    hostname: str|None = None
    host_registered: int|None = None
    model_config = ConfigDict(extra="ignore") # allow additional keys

    @field_validator('user_registered', mode='before')
    @classmethod
    def convert_decimal_to_int(cls, v):
        """Convert Decimal values to int for integer fields."""
        return convert_dynamodb_value(v)


class Session(DictLikeModel):
    """e11-sessions table record"""
    sid: str
    email: str                  # used to find the user in the Users table
    session_created: int
    session_expire: int
    claims: dict[str, Any] | None
    model_config = ConfigDict(extra="ignore") # allow additional keys

    @field_validator('session_created', 'session_expire', mode='before')
    @classmethod
    def convert_decimal_to_int(cls, v):
        """Convert Decimal values to int for integer fields."""
        return convert_dynamodb_value(v)

def convert_dynamodb_item(item: dict) -> dict:
    """Convert DynamoDB item values to proper Python types."""
    return {k: convert_dynamodb_value(v) for k, v in item.items()}


def make_course_key():
    """Make a course key"""
    return str(uuid.uuid4())[0:COURSE_KEY_LEN]

def create_new_user(email, claims=None):
    """Create a new user. claims must include 'email'"""
    now = int(time.time())
    user_id = str(uuid.uuid4())
    user = {
        A.USER_ID: user_id,
        A.SK: A.SK_USER,
        A.EMAIL: email,
        A.COURSE_KEY: make_course_key(),
        A.USER_REGISTERED: now,
        A.CLAIMS: claims,
    }
    users_table.put_item(Item=user)  # USER CREATION POINT
    return user

def get_user_from_email(email) -> User:
    """Given an email address, get the DynamoDB user record from the users_table.
    Note - when the first session is created, we don't know the user-id.
    """
    logger = get_logger()
    logger.debug("get_user_from_email: looking for email=%s", email)
    resp = users_table.query(
        IndexName="GSI_Email", KeyConditionExpression=Key("email").eq(email)
    )
    logger.debug("get_user_from_email: query result count=%s", resp["Count"])
    if resp["Count"] > 1:
        raise DatabaseInconsistency(
            f"multiple database entries with the same email: {resp}"
        )
    if resp["Count"] != 1:
        raise EmailNotRegistered(email)
    item = resp["Items"][0]
    logger.debug("get_user_from_email - item=%s", item)
    return User(**convert_dynamodb_item(item))


def add_user_log(event, user_id, message, **extra):
    """
    :param user_id: user_id
    :param message: Message to add to log
    """
    logger = get_logger()
    if event is not None:
        client_ip  = event["requestContext"]["http"]["sourceIp"]          # canonical client IP
    else:
        client_ip = extra.get('client_ip')
    now = datetime.datetime.now().isoformat()
    logger.debug("client_ip=%s user_id=%s message=%s extra=%s",client_ip, user_id, message, extra)
    ret = users_table.put_item(Item={A.USER_ID:user_id,
                                     A.SK:f'{A.SK_LOG_PREFIX}{now}',
                                     'client_ip':client_ip,
                                     'message':message,
                                     **extra})
    logger.debug("put_table=%s",ret)


def add_grade(user, lab, public_ip, summary):
    # Record grades
    logger = get_logger()
    now = datetime.datetime.now().isoformat()
    item = {
        A.USER_ID: user.user_id,
        A.SK: A.SK_GRADE_PATTERN.format(lab=lab, now=now),
        A.LAB: lab,
        A.PUBLIC_IP: public_ip,
        A.SCORE: str(summary["score"]),
        "pass_names": summary["passes"],
        "fail_names": summary["fails"],
        "raw": json.dumps(summary, default=str)[:35000],
    }
    ret = users_table.put_item(Item=item)
    logger.info("add_grade to %s user=%s ret=%s", users_table, user, ret)

def queryscan_table(what, kwargs):
    """use the users table and return the items"""
    kwargs = copy.copy(kwargs)  # it will be modified
    items = []
    while True:
        response = what(**kwargs)
        items.extend(response.get('Items',[]))
        lek = response.get('LastEvaluatedKey')
        if not lek:
            break
        kwargs['ExclusiveStartKey'] = lek
    return items

def get_grade(user, lab):
    """gets the highest grade for a user/lab"""
    kwargs:dict = {
        'KeyConditionExpression' : (
            Key(A.USER_ID).eq(user.user_id) &
            Key(A.SK).begins_with(f'{A.SK_GRADE_PREFIX}{lab}#') ),
        'ProjectionExpression' : f'{A.USER_ID}, {A.SK}, {A.SCORE}'
    }
    items = queryscan_table(users_table.query, kwargs)
    if items:
        score = max( (int(item.get(A.SCORE, 0)) for item in items) )
    else:
        score = 0
    return int(score)


def send_email(to_addr: str, email_subject: str, email_body: str):
    r = ses_client.send_email(
        Source=SES_VERIFIED_EMAIL,
        Destination={"ToAddresses": [to_addr]},
        Message={
            "Subject": {"Data": email_subject},
            "Body": {"Text": {"Data": email_body}},
        },
    )
    get_logger().info( "send_email to=%s subject=%s SES response: %s",
                       to_addr, email_subject, r )
    return r
