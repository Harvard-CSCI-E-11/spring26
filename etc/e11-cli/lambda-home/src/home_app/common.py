"""
Common includes for lambda-home.
"""

import os
import os.path
import sys
import logging
import functools
import datetime
from decimal import Decimal
from os.path import dirname, join, isdir
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, field_validator
import boto3

from mypy_boto3_route53.client import Route53Client
from mypy_boto3_secretsmanager.client import SecretsManagerClient
from mypy_boto3_dynamodb.client import DynamoDBClient
from mypy_boto3_dynamodb.service_resource import (
    DynamoDBServiceResource,
    Table as DynamoDBTable,
)

COURSE_DOMAIN = 'csci-e-11.org'
COOKIE_NAME = os.environ.get("COOKIE_NAME", "AuthSid")
COOKIE_SECURE = True
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN",COURSE_DOMAIN)
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")  # Lax|Strict|None


# fix the path. Don't know why this is necessary
MY_DIR = dirname(__file__)
sys.path.append(MY_DIR)

NESTED = join(MY_DIR, ".aws-sam", "build", "E11HomeFunction")
if isdir(join(NESTED, "e11")):
    sys.path.insert(0, NESTED)

TEMPLATE_DIR = join(MY_DIR,"templates")
STATIC_DIR = join(MY_DIR,"static")

# DynamoDB
DDB_REGION = os.environ.get("DDB_REGION","us-east-1")
USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME","e11-users")
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME","home-app-sessions")
SESSION_TTL_SECS    = int(os.environ.get("SESSION_TTL_SECS", str(60*60*24*180)))  # 180 days
dynamodb_client : DynamoDBClient= boto3.client("dynamodb")
dynamodb_resource : DynamoDBServiceResource = boto3.resource( 'dynamodb', region_name=DDB_REGION ) # our dynamoDB is in region us-east-1
users_table : DynamoDBTable   = dynamodb_resource.Table(USERS_TABLE_NAME)
sessions_table: DynamoDBTable = dynamodb_resource.Table(SESSIONS_TABLE_NAME)
route53_client :Route53Client = boto3.client('route53')
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


################################################################
### Logger
@functools.cache                # singleton
def _configure_root_once():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Configure a dedicated app logger; avoid touching the root logger.
    app_logger = logging.getLogger("e11")
    app_logger.setLevel(level)

    if not app_logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s [%(name)s %(filename)s:%(lineno)d %(funcName)s] %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        app_logger.addHandler(handler)

    # Prevent bubbling to root (stops double logs)
    app_logger.propagate = False

    # If this code is used as a library elsewhere, avoid “No handler” warnings:
    logging.getLogger(__name__).addHandler(logging.NullHandler())

def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger under the 'e11' namespace (e.g., e11.grader)."""
    _configure_root_once()
    return logging.getLogger("e11" + ("" if not name else f".{name}"))



################################################################
## Add to user log
LOGGER = get_logger("grader")

def add_user_log(event, user_id, message, **extra):
    """
    :param user_id: user_id
    :param message: Message to add to log
    """
    if event is not None:
        client_ip  = event["requestContext"]["http"]["sourceIp"]          # canonical client IP
    else:
        client_ip = extra.get('client_ip')
    now = datetime.datetime.now().isoformat()
    LOGGER.debug("client_ip=%s user_id=%s message=%s extra=%s",client_ip, user_id, message, extra)
    ret = users_table.put_item(Item={A.USER_ID:user_id,
                                     'sk':f'{A.SK_LOG_PREFIX}{now}',
                                     'client_ip':client_ip,
                                     'message':message,
                                     **extra})
    LOGGER.debug("put_table=%s",ret)

# Staging environment configuration
def is_staging_environment(event) -> bool:
    """Detect if we're running in the staging environment"""
    stage = event.get("requestContext", {}).get("stage", "")
    return stage == "stage"


def make_cookie(name:str, value: str, max_age: int = SESSION_TTL_SECS, clear: bool = False, domain = None) -> str:
    """ create a cookie for Lambda """
    parts = [f"{name}={'' if clear else value}"]
    if domain:
        parts.append(f"Domain={domain}")
    parts.append("Path=/")
    if COOKIE_SECURE:
        parts.append("Secure")
    parts.append("HttpOnly")
    parts.append(f"SameSite={COOKIE_SAMESITE}")
    if clear:
        parts.append("Max-Age=0")
        parts.append("Expires=Thu, 01 Jan 1970 00:00:00 GMT")
    else:
        parts.append(f"Max-Age={max_age}")
    return "; ".join(parts)

def get_cookie_domain(event) -> str:
    """Get the appropriate cookie domain based on the environment"""
    if is_staging_environment(event):
        # In staging, always use the production domain for cookies
        # so sessions work across both environments
        return COURSE_DOMAIN
    return COOKIE_DOMAIN
