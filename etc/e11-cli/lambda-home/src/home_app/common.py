"""
Common includes for lambda-home.
"""

import os
import os.path
import sys
import logging
import functools
import datetime
from os.path import dirname, join, isdir

import boto3

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
dynamodb_client = boto3.client("dynamodb")
dynamodb_resource = boto3.resource( 'dynamodb', region_name=DDB_REGION ) # our dynamoDB is in region us-east-1
users_table    = dynamodb_resource.Table(USERS_TABLE_NAME)
sessions_table = dynamodb_resource.Table(SESSIONS_TABLE_NAME)

# attributes

class A:
    SESSION_CREATED='session_created'
    SESSION_EXPIRE='session_expire'
    USER_ID = 'user_id'
    EMAIL = 'email'
    IPADDR = 'ipaddr'           # public IP address
    NAME = 'name'               # Name the user prefers, not the name in the claims
    HOSTNAME = 'hostname'
    REG_TIME = 'reg_time'
    COURSE_KEY = 'course_key'
    CLAIMS = 'claims'
    CREATED = 'created'         # time_t
    UPDATED = 'updated'         # time_t
    SK = 'sk'                   # sort key
    SK_USER = '#'               # sort key for the user record
    SK_LOG_PREFIX = 'log#'         # sort key prefix for log entries
    SK_GRADE_PREFIX = 'grade#'         # sort key prefix for log entries



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

    _CONFIGURED = True

def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger under the 'e11' namespace (e.g., e11.grader)."""
    _configure_root_once()
    return logging.getLogger("e11" + ("" if not name else f".{name}"))


def smash_email(email):
    """Convert an email into the CSCI E-11 smashed email"""
    email    = re.sub(r'[^-a-zA-Z0-9_@.+]', '', email).lower().strip()
    smashed_email = "".join(email.replace("@",".").split(".")[0:2])
    return smashed_email


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
