"""
Common includes for lambda-home.
"""

import os
import sys
from os.path import dirname, join, isdir

from e11.e11core.constants import COURSE_DOMAIN

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
## Add to user log
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
