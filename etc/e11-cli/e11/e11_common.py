"""
Common includes for E11 DynamoDB
"""

import os
import time
import uuid
from decimal import Decimal
from typing import Any, Dict, Optional, TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, field_validator
import boto3

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

COURSE_NAME   = 'CSCI E-11'
COURSE_DOMAIN = 'csci-e-11.org'
COURSE_KEY_LEN = 6


# DynamoDB config
DDB_REGION = os.environ.get("DDB_REGION","us-east-1")
USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME","e11-users")
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME","home-app-sessions")

# DynamoDB values:
dynamodb_client : DynamoDBClient = boto3.client("dynamodb")
dynamodb_resource : DynamoDBServiceResource = boto3.resource( 'dynamodb', region_name=DDB_REGION )
users_table : DynamoDBTable   = dynamodb_resource.Table(USERS_TABLE_NAME)
sessions_table: DynamoDBTable = dynamodb_resource.Table(SESSIONS_TABLE_NAME)
route53_client : Route53Client = boto3.client('route53')
secretsmanager_client : SecretsManagerClient = boto3.client("secretsmanager")

# Classes

class DatabaseInconsistency(RuntimeError):
    pass

class EmailNotRegistered(RuntimeError):
    pass

class InvalidCookie(RuntimeError):
    pass

# attributes

class A:
    SESSION_CREATED='session_created'
    SESSION_EXPIRE='session_expire'
    USER_ID = 'user_id'
    EMAIL = 'email'
    PUBLIC_IP = 'public_ip'           # public IP address
    PREFERRED_NAME = 'preferred_name'
    HOSTNAME = 'hostname'
    COURSE_KEY = 'course_key'
    CLAIMS = 'claims'
    SESSION_CREATED = 'session_created'  # time_t
    SESSION_EXPIRE = 'session_expire'    # time_t
    USER_REGISTERED = 'user_registered'
    HOST_REGISTERED = 'host_registered'
    LAB = 'lab'
    SK = 'sk'                   # sort key
    SK_USER = '#'               # sort key for the user record
    SK_LOG_PREFIX = 'log#'         # sort key prefix for log entries
    SK_GRADE_PREFIX = 'grade#'         # sort key prefix for log entries


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
    preferred_name: Optional[str] = None
    claims: Dict[str, Any]
    public_ip: Optional[str] = None
    hostname: Optional[str] = None
    host_registered: Optional[int] = None
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
    claims: Dict[str, Any]
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
