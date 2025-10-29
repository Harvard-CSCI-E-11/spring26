"""
Sessions Management
"""

# at top of home_app/home.py (module import time)
import uuid
import time

from typing import Optional

from boto3.dynamodb.conditions import Key

from .common import DatabaseInconsistency, EmailNotRegistered, convert_dynamodb_item
from .common import get_logger, add_user_log
from .common import users_table, sessions_table, SESSION_TTL_SECS, A
from .common import User, Session, get_cookie_domain, COOKIE_NAME

LOGGER = get_logger("home")
COURSE_KEY_LEN = 6


# Auth Cookie


################################################################
## session management - sessions are signed cookies that are stored in the DynamoDB
##


def make_course_key():
    """Make a course key"""
    return str(uuid.uuid4())[0:COURSE_KEY_LEN]


def parse_cookies(event) -> dict:
    """Extract the cookies from HTTP API v2 event"""
    cookie_list = event.get("cookies") or []
    cookies = {}
    for c in cookie_list:
        if "=" in c:
            k, v = c.split("=", 1)
            cookies[k] = v
    return cookies


def create_new_user(event, claims):
    """Create a new user. claims must include 'email'"""
    now = int(time.time())
    user_id = str(uuid.uuid4())
    user = {
        A.USER_ID: user_id,
        A.SK: A.SK_USER,
        A.EMAIL: claims["email"],
        A.COURSE_KEY: make_course_key(),
        A.USER_REGISTERED: now,
        A.CLAIMS: claims,
    }
    users_table.put_item(Item=user)  # USER CREATION POINT
    add_user_log(event, user_id, f"User {claims['email']} created", claims=claims)
    return user_id


def get_user_from_email(email) -> User:
    """Given an email address, get the DynamoDB user record from the users_table.
    Note - when the first session is created, we don't know the user-id.
    """
    LOGGER.debug("get_user_from_email: looking for email=%s", email)
    resp = users_table.query(
        IndexName="GSI_Email", KeyConditionExpression=Key("email").eq(email)
    )
    LOGGER.debug("get_user_from_email: query result count=%s", resp["Count"])
    if resp["Count"] > 1:
        raise DatabaseInconsistency(
            f"multiple database entries with the same email: {resp}"
        )
    if resp["Count"] != 1:
        raise EmailNotRegistered(email)
    item = resp["Items"][0]
    LOGGER.debug("get_user_from_email: found item with keys=%s", list(item.keys()))
    LOGGER.debug("get_user_from_email - item=%s", item)
    return User(**convert_dynamodb_item(item))


def new_session(event, claims) -> Session:
    """Create a new session from the OIDC claims and store in the DyanmoDB table.
    The esid (email plus session identifier) is {email}:{uuid}
    Get the USER_ID from the users table. If it is not there, create it.
    Returns the Session object.
    """
    client_ip = event["requestContext"]["http"]["sourceIp"]  # canonical client IP
    LOGGER.debug("in new_session. claims=%s client_ip=%s", claims, client_ip)
    email = claims[A.EMAIL]

    try:
        user = get_user_from_email(email)
        user_id = user.user_id
    except EmailNotRegistered:
        # User doesn't exist, create new user
        user_id = create_new_user(event, claims)

    sid = str(uuid.uuid4())
    session = {
        "sid": sid,
        "email": email,
        A.SESSION_CREATED: int(time.time()),
        A.SESSION_EXPIRE: int(time.time() + SESSION_TTL_SECS),
        "client_ip": client_ip,
        "claims": claims,
    }
    ret = sessions_table.put_item(Item=session)
    LOGGER.debug(
        "new_session table=%s user=%s session=%s ret=%s",
        sessions_table,
        user,
        session,
        ret,
    )
    add_user_log(event, user_id, f"Session {sid} created")
    return Session(**session)


def get_session_from_sid(event, sid) -> Optional[Session]:
    LOGGER.debug(
        "get_session_from_sid sid=%s get_cookie_domain(%s)=%s",
        sid,
        event,
        get_cookie_domain(event),
    )
    if not sid:
        return None
    resp = sessions_table.get_item(Key={"sid": sid})
    LOGGER.debug("get_session sid=%s resp=%s", sid, resp)
    item = resp.get("Item")
    if item is None:
        return None
    ses = Session(**convert_dynamodb_item(item))
    now = int(time.time())
    if not ses:
        LOGGER.debug("get_session no ses")
        return None
    if ses.session_expire <= now:
        # Session has expired. Delete it and return none
        LOGGER.debug(
            "Deleting expired sid=%s session_expire=%s now=%s",
            sid,
            ses.session_expire,
            now,
        )
        sessions_table.delete_item(Key={"sid": sid})
        add_user_log(event, "unknown", f"Session {sid} expired")
        return None
    LOGGER.debug("get_session session=%s", ses)
    return ses


def get_session_from_event(event) -> Optional[Session]:
    """Return the session dictionary if the session is valid and not expired.
    Sessions are determined by having the session cookie"""
    return get_session_from_sid(event, parse_cookies(event).get(COOKIE_NAME))


def all_sessions_for_email(email):
    """Return all of the sessions for an email address"""
    resp = sessions_table.query(
        IndexName="GSI_Email",
        KeyConditionExpression="email = :e",
        ExpressionAttributeValues={":e": email},
    )
    sessions = resp["Items"]
    return sessions


def delete_session(sid):
    LOGGER.info("delete_session sid=%s", sid)
    return sessions_table.delete_item(Key={"sid": sid})


def delete_session_from_event(event):
    """Delete the session, whether it exists or not"""
    sid = parse_cookies(event).get(COOKIE_NAME)
    if sid:
        return delete_session(sid)
    return None


def expire_batch(now: int, items: list) -> int:
    """Actually delete the items"""
    n = 0
    for item in items:
        if item.get("session_expire", 0) <= now:
            sessions_table.delete_item(Key={"sid": item["sid"]})
            n += 1
    return n
