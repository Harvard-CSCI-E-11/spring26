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
import base64
from zoneinfo import ZoneInfo
from decimal import Decimal
from typing import Any, TYPE_CHECKING
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator
import boto3
from boto3.dynamodb.conditions import Key

from e11.e11core.constants import COURSE_KEY_LEN, COURSE_DOMAIN
from e11.e11core.utils import get_logger

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client
    from mypy_boto3_route53 import Route53Client
    from mypy_boto3_secretsmanager import SecretsManagerClient
    from mypy_boto3_dynamodb import DynamoDBClient
    from mypy_boto3_dynamodb.service_resource import DynamoDBServiceResource, Table as DynamoDBTable
    from mypy_boto3_sqs.client import SQSClient
else:
    S3Client = Any                 # pylint: disable=invalid-name
    Route53Client = Any            # pylint: disable=invalid-name
    SecretsManagerClient = Any     # pylint: disable=invalid-name
    DynamoDBClient = Any           # pylint: disable=invalid-name
    DynamoDBServiceResource = Any  # pylint: disable=invalid-name
    DynamoDBTable = Any            # pylint: disable=invalid-name
    SQSClient = Any                 # pylint: disable=invalid-name

# COURSE_KEY_LEN and COURSE_DOMAIN are imported from e11.e11core.constants

S3_BUCKET  = 'csci-e-11'
AWS_REGION = 'us-east-1'
DASHBOARD = f"https://{COURSE_DOMAIN}"
DNS_TTL = 30

# Route53
HOSTED_ZONE_ID = "Z05034072HOMXYCK23BRA"  # Route53 hosted zone for course domain

# SSH/Bot Configuration
CSCIE_BOT = "cscie-bot"
CSCIE_BOT_KEYFILE = 'csci-e-11-bot.pub'

# GitHub Repository
GITHUB_REPO_URL = "https://github.com/Harvard-CSCI-E-11/spring26"

# Lab Configuration
# Each lab has a redirect URL and a deadline (ISO-8601 format, Eastern time, no timezone)

LAB_TIMEZONE = ZoneInfo("America/New_York")  # Eastern timezone for lab deadlines

LAB_CONFIG = {
    "lab0": {
        "redirect": "https://docs.google.com/document/d/1ywWJy6i2BK1qDZcWMWXXFibnDtOmeWFqX1MomPFYEN4/edit?usp=drive_link",
        "deadline": "2026-02-02T23:59:59"
    },
    "lab1": {
        "redirect": "https://docs.google.com/document/d/1okJLytuKSqsq0Dz5GUZHhEVj0UqQoWRTsxCac1gWiW4/edit?usp=drive_link",
        "deadline": "2026-02-09T23:59:59"
    },
    "lab2": {
        "redirect": "https://docs.google.com/document/d/1-3Wrh1coGqYvgfIbGvei8lw3XJQod85zzuvfdMStsvs/edit?usp=drive_link",
        "deadline": "2026-02-16T23:59:59"
    },
    "lab3": {
        "redirect": "https://docs.google.com/document/d/1pOeS03gJRGaUTezjs4-K6loY3SoVx4xRYk6Prj7WClU/edit?usp=drive_link",
        "deadline": "2026-02-23T23:59:59"
    },
    "lab4": {
        "redirect": "https://docs.google.com/document/d/1CW48xvpbEE9xPs_6_2cQjOQ4A7xvWgoWCEMgkPjNDuc/edit?usp=drive_link",
        "deadline": "2026-03-09T23:59:59"
    },
    "lab5": {
        "redirect": "https://docs.google.com/document/d/1mZOBtyqlpK4OGCXZ80rCWK0ryZ53hNBxL_m-urWzslg/edit?usp=drive_link",
        "deadline": "2026-03-30T23:59:59"
    },
    "lab6": {
        "redirect": "https://docs.google.com/document/d/1aRFFRaWmMrmgn3ONQDGhYghC-823GbGzAP-7qdt5E0U/edit?usp=drive_link",
        "deadline": "2026-04-13T23:59:59"
    },
    "lab7": {
        "redirect": "https://docs.google.com/document/d/14RdMZr3MYGiazjtEklW-cYWj27ek8YV2ERFOblZhIoM/edit?usp=drive_link",
        "deadline": "2026-04-27T23:59:59"
    },
    "lab8": {
        "redirect": "https://docs.google.com/document/d/1WEuKLVKmudsOgrpEqaDvIHE55kWKZDqAYbEvPWaA4gY/edit?usp=drive_link",
        "deadline": "2026-05-11T23:59:59"
    }
}

# Backward compatibility: LAB_REDIRECTS for existing code
LAB_REDIRECTS = {i: LAB_CONFIG[f"lab{i}"]["redirect"] for i in range(9)}

EMAIL_BODY = """
    Hi {preferred_name},

    You have successfully registered your AWS instance.

    Your course key is: {course_key}

    The following DNS record has been created:

    Hostname: {hostname}
    Public IP Address: {public_ip}

    Best regards,
    CSCIE-11 Team
"""



# Time Constants
SIX_MONTHS = 60 * 60 * 24 * 180  # 180 days in seconds

# DynamoDB config
USERS_TABLE_NAME    = os.environ.get("USERS_TABLE_NAME","e11-users")
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME","home-app-sessions")
IMAGE_BUCKET_NAME   = S3_BUCKET

# DynamoDB
dynamodb_client : DynamoDBClient = boto3.client("dynamodb", region_name=AWS_REGION)
dynamodb_resource : DynamoDBServiceResource = boto3.resource( 'dynamodb', region_name=AWS_REGION )
users_table : DynamoDBTable   = dynamodb_resource.Table(USERS_TABLE_NAME)
sessions_table: DynamoDBTable = dynamodb_resource.Table(SESSIONS_TABLE_NAME)
route53_client : Route53Client = boto3.client('route53', region_name=AWS_REGION)
secretsmanager_client : SecretsManagerClient = boto3.client("secretsmanager", region_name=AWS_REGION)
sqs_client :SQSClient = boto3.client("sqs", region_name=AWS_REGION)

# S3
s3_client : S3Client = boto3.client("s3", region_name=AWS_REGION)

# Simple Email Service
SES_VERIFIED_EMAIL = f"admin@{COURSE_DOMAIN}"  # Verified SES email address
ses_client = boto3.client("ses", region_name=AWS_REGION)

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
    BUCKET = 'bucket'           # for S3
    EMAIL = 'email'
    HOSTNAME = 'hostname'
    HOST_REGISTERED = 'host_registered'
    LAB = 'lab'
    PREFERRED_NAME = 'preferred_name'
    PUBLIC_IP = 'public_ip'           # public IP address
    SCORE = 'score'
    SESSION_CREATED = 'session_created'  # time_t
    SESSION_EXPIRE = 'session_expire'    # time_t
    KEY = 'key'                          # typically for S3
    SK = 'sk'                   # sort key
    SK_GRADE_PREFIX = 'grade#'         # sort key prefix for log entries
    SK_GRADE_PATTERN = SK_GRADE_PREFIX + "{lab}#{now}"
    SK_LOG_PREFIX = 'log#'         # sort key prefix for log entries
    SK_USER = '#'                  # sort key for the user record
    SK_IMAGE_PREFIX = 'image#'     # sort key for images
    SK_IMAGE_PATTERN = SK_IMAGE_PREFIX + "{lab}#{now}"
    SK_LEADERBOARD_LOG_PREFIX = 'leaderboard-log#' # leaderboard-log
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

def queryscan_table(what, kwargs):
    """Query or Scan a DynamoDB table, returning all matching items.
    :param what:  should be users_table.scan, users_table.query, etc.
    :param kwargs: should be the args that are used for the query or scan.
    """
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

################################################################

class DictLikeModel(BaseModel):
    def __getitem__(self, key: str):
        return getattr(self, key)

class User(DictLikeModel):
    """e11-users table sk='#' record"""
    user_id: str
    sk: str
    email: str|None = None      # not all records have email
    course_key: str|None = None
    user_registered: int|None = None
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

def generate_direct_login_url(user_id: str, course_key: str) -> str:
    """Generate direct login URL with base64-encoded token.

    Args:
        user_id: User ID from the database
        course_key: Course key for the user

    Returns:
        Full URL for direct login: https://{domain}/login-direct?token={base64_token}
    """

    # Create token: user_id:course_key
    token_data = f"{user_id}:{course_key}"
    # Base64 encode (URL-safe, strip padding)
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')

    return f"https://{COURSE_DOMAIN}/login-direct?token={token}"

################################################################
## user table - user management

def create_new_user(email, claims=None):
    """Create a new user."""
    now = int(time.time())
    user_id = str(uuid.uuid4())
    # Fail if public_ip is in claims - it should not be in claims
    # Claims are OIDC identity fields (email, name, etc.), not instance-specific fields
    if claims is not None and A.PUBLIC_IP in claims:
        raise ValueError(
            f"public_ip should not be in claims. Claims are OIDC identity fields "
            f"(email, name, etc.), not instance-specific fields. "
            f"Found public_ip='{claims[A.PUBLIC_IP]}' in claims for email='{email}'"
        )
    user = {
        A.USER_ID: user_id,
        A.SK: A.SK_USER,
        A.EMAIL: email,
        A.COURSE_KEY: make_course_key(),
        A.USER_REGISTERED: now,
        A.CLAIMS: claims,
    }
    users_table.put_item(Item=user)  # USER CREATION POINT
    return User(**convert_dynamodb_item(user))

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

def get_user_from_user_id(user_id: str) -> User:
    """Get user record by user_id."""
    logger = get_logger()
    logger.debug("get_user_from_user_id: looking for user_id=%s", user_id)
    resp = users_table.get_item(
        Key={A.USER_ID: user_id, A.SK: A.SK_USER}
    )
    if "Item" not in resp:
        raise EmailNotRegistered(f"User {user_id} not found")
    item = resp["Item"]
    logger.debug("get_user_from_user_id - item=%s", item)
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
    now = datetime.now().isoformat()
    logger.debug("client_ip=%s user_id=%s message=%s extra=%s",client_ip, user_id, message, extra)
    ret = users_table.put_item(Item={A.USER_ID:user_id,
                                     A.SK:f'{A.SK_LOG_PREFIX}{now}',
                                     'client_ip':client_ip,
                                     'message':message,
                                     **extra})
    logger.debug("put_table=%s",ret)

################################################################
## grading

def add_grade(user, lab, public_ip, summary):
    # Record grades
    now = datetime.now().isoformat()
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
    get_logger().info("add_grade to %s user=%s ret=%s", users_table, user, ret)

def get_grade(user, lab):
    """gets the highest grade for a user/lab"""
    kwargs = {
        'KeyConditionExpression' : (
            Key(A.USER_ID).eq(user.user_id) &
            Key(A.SK).begins_with(f'{A.SK_GRADE_PREFIX}{lab}#') ),
        'ProjectionExpression' : f'{A.USER_ID}, {A.SK}, {A.SCORE}'
    }
    items = queryscan_table(users_table.query, kwargs)
    if items:
        score = max( (float(item.get(A.SCORE, 0)) for item in items) )
    else:
        score = 0
    return float(score)

################################################################
## image stuff

def add_image(user_id, lab, bucket, key):
    now = datetime.now().isoformat()
    item = {
        A.USER_ID: user_id,
        A.SK: A.SK_IMAGE_PATTERN.format(lab=lab, now=now),
        A.BUCKET: bucket,
        A.LAB: lab,
        A.KEY: key,
    }
    ret = users_table.put_item(Item=item)
    get_logger().info("add_image user_id=%s bucket=%s key=%s ret=%s", user_id, bucket, key, ret)

def get_images(user_id):
    kwargs = {'KeyConditionExpression' : (
	Key(A.USER_ID).eq(user_id) &
        Key(A.SK).begins_with(A.SK_IMAGE_PREFIX)
    )}
    return queryscan_table(users_table.query, kwargs)

def delete_image(user_id, sk, bucket, key):
    get_logger().info("delete_image user=%s sk=%s bucket=%s key=%s", user_id, sk, bucket, key)
    r1 = users_table.delete_item(Key={A.USER_ID:user_id, A.SK:sk})
    r2 = s3_client.delete_object(Bucket=bucket, Key=key)
    get_logger().info("delete_image r1=%s r2=%s", r1, r2)

################################################################
## leaderboard stuff

def add_leaderboard_log(user_id, client_ip, name, user_agent, **extra):
    """
    :param user_id: user_id
    :param message: Message to add to log
    """
    logger = get_logger()
    now = datetime.now().isoformat()
    logger.debug("client_ip=%s user_id=%s name=%s user_agent=%s",client_ip, user_id, name, user_agent)
    ret = users_table.put_item(Item={A.USER_ID:user_id,
                                     A.SK:f'{A.SK_LEADERBOARD_LOG_PREFIX}{now}',
                                     'client_ip':client_ip,
                                     'name':name,
                                     'user_agent':user_agent,
                                     **extra})
    logger.debug("put_table=%s",ret)


################################################################
## SES
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
