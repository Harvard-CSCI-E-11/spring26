"""
Common includes for E11 DynamoDB.
Defines datamodel and simple access routines.
Used by both AWS Lambda and by e11 running in E11_STAFF mode (where staff interact directly with DynamoDB table using their AWS credentials.)
"""

import os
import time
import uuid
from decimal import Decimal
from typing import Any, TYPE_CHECKING

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
    SESSION_CREATED = 'session_created'  # time_t
    SESSION_EXPIRE = 'session_expire'    # time_t
    SK = 'sk'                   # sort key
    SK_GRADE_PREFIX = 'grade#'         # sort key prefix for log entries
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
