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

from e11.e11_common import COURSE_DOMAIN, users_table, A

SESSION_TTL_SECS    = int(os.environ.get("SESSION_TTL_SECS", str(60*60*24*180)))  # 180 days
DNS_TTL = 30
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
