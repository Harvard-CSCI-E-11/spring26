"""
Generate the https://csci-e-11.org/ home page.
Runs OIDC authentication for Harvard Key.
Supports logging in and logging out.
Allows users to see all active sessions and results of running the grader.

Data Model:
Users table:
PK: user#<user_id>
SK: PROFILE (and other items as needed)

Sessions table:
PK: SID#<sid>
Item: object including email, and user_id

Cookies - just have sid (session ID)

"""

import base64
import json
import os
import sys
import binascii
import uuid
import time
import logging
from typing import Any, Dict, Tuple, Optional

LOGGER = logging.getLogger("e11.grader")
if not LOGGER.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(h)
try:
    LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))
except ValueError:
    LOGGER.setLevel(logging.INFO)

LOGGER.info("sys.path=%s",sys.path)
LOGGER.info("pwd=%s",os.getcwd())


TASK_DIR = os.path.dirname(__file__)        # typically /var/task
NESTED = os.path.join(TASK_DIR, ".aws-sam", "build", "E11HomeFunction")

LOGGER.info("TASK_DIR=%s",TASK_DIR)
LOGGER.info("NESTED=%s",NESTED)

if not os.path.isdir(os.path.join(TASK_DIR, "e11")) and os.path.isdir(os.path.join(NESTED, "e11")):
    # put the nested dir first so `import e11` resolves
    sys.path.insert(0, NESTED)


from jinja2 import Environment,FileSystemLoader
from itsdangerous import BadSignature, SignatureExpired
import boto3
import common
import oidc                     # pylint: disable=wrong-import-position
# ---------- logging setup ----------


LOGGER    = common.LOGGER

OIDC_SECRET_ID = os.environ.get("OIDC_SECRET_ID")
DDB_TABLE_ARN = os.environ.get("DDB_TABLE_ARN")
DDB_REGION = os.environ.get("DDB_REGION","us-east-1")
COOKIE_NAME = os.environ.get("COOKIE_NAME", "AuthSid")
COOKIE_SECURE = True
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN",'csci-e-11.org')
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")  # Lax|Strict|None
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME")
SESSION_TTL_SECS = int(os.environ.get("SESSION_TTL_SECS", str(60*60*24*180)))  # 180 days
SES_VERIFIED_EMAIL = "admin@csci-e-11.org"      # Verified SES email address
HOSTED_ZONE_ID = "Z05034072HOMXYCK23BRA"        # from route53

EMAIL_BODY="""
    You have successfully registered your AWS instance.

    Your course key is: {course_key}

    The following DNS record has been created:

    Hostname: {hostname}
    IP Address: {ip_address}

    Best regards,
    CSCIE-11 Team
"""


ses_client = boto3.client("ses")
_boto_ddb = boto3.client("dynamodb")
_boto_secrets = boto3.client("secretsmanager")

env = Environment(loader=FileSystemLoader(["templates",common.TEMPLATE_DIR,os.path.join(common.NESTED,"templates")]))

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1] if arn and ":table/" in arn else arn

dynamodb_resource = boto3.resource( 'dynamodb', region_name=DDB_REGION ) # our dynamoDB is in region us-east-1
table = dynamodb_resource.Table(_ddb_table_name_from_arn(DDB_TABLE_ARN))
sessions_table = dynamodb_resource.Table(SESSIONS_TABLE_NAME)


def _resp_json(status: int, body: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
    LOGGER.debug("_resp_json(status=%s)",status)
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": json.dumps(body),
    }

def _resp_text(status: int, body: str, headers: Dict[str, str] = None, cookies: Dict[str, str]=None) -> Dict[str, Any]:
    LOGGER.debug("_resp_text(status=%s)",status)
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": body,
        "cookies": cookies or [],
    }

def _redirect(location:str, extra_headers: Optional[dict] = None, cookies: Optional[list]=None):
    LOGGER.debug("_redirect(%s,%s,%s)",location,extra_headers,cookies)
    headers = {"Location": location}
    if extra_headers:
        headers.update(extra_headers)
    return {
        "statusCode": 302,
        "headers": headers,
        "cookies": cookies or [],
        "body" : ""
    }

def _with_request_log_level(payload: Dict[str, Any]):
    """Context manager to temporarily adjust log level from JSON (log_level or LOG_LEVEL)."""
    class _Ctx:
        def __init__(self):
            self.old = LOGGER.level

        def __enter__(self):
            lvl = payload.get("log_level") or payload.get("LOG_LEVEL")
            if isinstance(lvl, str):
                LOGGER.setLevel(lvl)
            return self
        def __exit__(self, exc_type, exc, tb):
            LOGGER.setLevel(self.old)
    return _Ctx()

################################################################
## Parse Lambda Events and cookies
def parse_event(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """ parser HTTP API v2 event"""
    stage = event.get("requestContext", {}).get("stage", "")
    path  = event.get("rawPath") or event.get("path") or "/"
    if stage and path.startswith("/" + stage):
        path = path[len(stage)+1:] or "/"
    method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", "GET"))
    body = event.get("body")
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body or "").decode("utf-8", "replace")
        except binascii.Error:
            body = None
    try:
        payload = json.loads(body) if body else {}
    except json.JSONDecodeError:
        payload = {}
    return method, path, payload

def parse_cookies(event) -> dict:
    """ Extract the cookies from HTTP API v2 event """
    cookie_list = event.get("cookies") or []
    cookies = {}
    for c in cookie_list:
        if "=" in c:
            k, v = c.split("=", 1)
            cookies[k] = v
    return cookies

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


################################################################
def get_odic_config():
    """Return the config from AWS Secrets"""
    harvard_secrets = json.loads(_boto_secrets.get_secret_value(SecretId=OIDC_SECRET_ID)['SecretString'])
    LOGGER.info("fetched secret %s keys: %s",OIDC_SECRET_ID,list(harvard_secrets.keys()))
    config = oidc.load_openid_config(harvard_secrets['oidc_discovery_endpoint'],
                                     client_id=harvard_secrets['client_id'],
                                     redirect_uri=harvard_secrets['redirect_uri'])
    return {**config,**harvard_secrets}

################################################################
## session management - sessions are signed cookies that are stored in the DynamoDB
##
def new_session(claims, client_ip):
    """Create a new session from the OIDC claims and store in the DyanmoDB table.
    The esid (email plus session identifier) is {email}:{uuid}
    """
    email = claims['email']
    sid = str(uuid.uuid4())
    sessions_table.put_item(Item={
        "sid": sid,
        "email": email,
        "time" : int(time.time()),
        "ttl"  : int(time.time()) + SESSION_TTL_SECS,
        "name" : claims.get('name',''),
        "client_ip": client_ip or "",
        "claims" : claims })
    return sid

def get_session(event) -> Optional[dict]:
    """Return the session dictionary if the session is valid and not expired."""
    sid = parse_cookies(event).get(COOKIE_NAME)
    if not sid:
        return None
    resp = sessions_table.get_item(Key={"sid":sid})
    item = resp.get("Item")
    now  = int(time.time())
    if not item:
        return None
    if item.get("ttl", 0) <= now:
        # Session has expired. Delete it and return none
        LOGGER.info("Deleting expired sid=%s ttl=%s now=%s",sid,item.get("ttl",0),now)
        sessions_table.delete_item(Key={"sid":sid})
        return None
    return item

def delete_session(event):
    """Delete the session, whether it exists or not"""
    sid = parse_cookies(event).get(COOKIE_NAME)
    if not sid:
        return
    sessions_table.delete_item(Key={"sid":sid})

def all_sessions_for_email(email):
    """Return all of the sessions for an email address"""
    resp = sessions_table.query(
        IndexName="GSI_Email",
        KeyConditionExpression="email = :e",
        ExpressionAttributeValues={":e":email},
    )
    sessions = resp["Items"]
    return sessions

################################################################
## http points

def do_home_page(event, status="",extra=""):
    """/"""
    # If there is an active session, redirect to the dashboard
    ses = get_session(event)
    if ses:
        LOGGER.debug("ses=%s redirecting to /dashboard",ses)
        return _redirect("/dashboard")
    # Build an authentication login
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.info("url=%s issued_at=%s",url,issued_at)
    template = env.get_template("index.html")
    return _resp_text(200, template.render(harvard_key=url, status=status, extra=extra))

def do_dashboard(event):
    """/dashboard"""
    ses = get_session(event)
    if not ses:
        LOGGER.debug("No session; redirect to /")
        return _redirect("/")

    # Show the dashboard
    template = env.get_template("dashboard.html")
    # TODO: Get all activate sessions and allow them to be deleted
    # TODO: Get all all activity
    return _resp_text(200, template.render())

def do_callback(event):
    """OIDC callback from Harvard Key website."""
    params = event.get("queryStringParameters") or {}
    LOGGER.info("callback params=%s",params)
    code = params.get("code")
    state = params.get("state")
    if not code:
        return { "statusCode": 400,
                 "body": "Missing 'code' in query parameters" }
    try:
        obj = oidc.handle_oidc_redirect_stateless(openid_config = get_odic_config(),
                                                  callback_params={'code':code,'state':state})
    except (SignatureExpired,BadSignature):
        return _redirect("/expired")

    LOGGER.info("obj=%s",obj)
    client_ip  = event["requestContext"]["http"]["sourceIp"]          # canonical client IP
    sid = new_session(obj['claims'],client_ip=client_ip)
    sid_cookie = make_cookie(COOKIE_NAME, sid, max_age=SESSION_TTL_SECS, domain=COOKIE_DOMAIN)
    return _redirect("/dashboard", cookies=[sid_cookie])

def do_logout(event):
    """/logout"""
    delete_session(event)
    del_cookie = make_cookie(COOKIE_NAME, "", clear=True)
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.info("url=%s issued_at=%s ",url,issued_at)
    return _resp_text(200, env.get_template("logout.html").render(harvard_key=url), cookies=[del_cookie])


def do_register(event):
    """Register a VM"""
    LOGGER.info("do_register event=%s",event)
    return _resp_json(400, {'error':True})

def do_grade(event):
    """Do a grade"""
    LOGGER.info("do_register event=%s",event)
    return _resp_json(400, {'error':True})

################################################################
## main entry point from lambda system

# pylint: disable=too-many-return-statements
def lambda_handler(event, context): # pylint: disable=unused-argument
    """called by lambda"""
    method, path, payload = parse_event(event)
    with _with_request_log_level(payload):
        try:
            LOGGER.info("req method='%s' path='%s' action='%s'", method, path, payload.get("action"))
            action = (payload.get("action") or "").lower()

            match (method, path, action):
                # JSON Actions
                case ("POST", "/", "ping"):
                    return _resp_json(200, {"error": False, "message": "ok", "path":sys.path, 'environ':dict(os.environ)})

                case ("POST", "/", "ping-mail"):
                    hostnames = ['first']
                    ip_address = 'address'
                    email_subject = "E11 email ping"
                    email_body = EMAIL_BODY.format(hostname=hostnames[0], ip_address=ip_address)
                    ses_response = ses_client.send_email(
                        Source=SES_VERIFIED_EMAIL,
                        Destination={'ToAddresses': [payload['email']]},
                        Message={ 'Subject': {'Data': email_subject},
                                  'Body': {'Text': {'Data': email_body}} } )
                    LOGGER.info("SES response: %s",ses_response)

                    return _resp_json(200, {"error": False, "message": "ok", "path":sys.path, 'environ':dict(os.environ)})

                case ("GET", "/", "register"):
                    return _resp_json(200, {"error": False, "message": "ok", "path":sys.path, 'environ':dict(os.environ)})

                # Human actions
                case ("GET","/", _):
                    return do_home_page(event)

                case ("GET","/auth/callback",_):
                    return do_callback(event)

                case ("GET","/dashboard",_):
                    return do_dashboard(event)

                case ("GET","/logout",_):
                    return do_logout(event)

                case (_,_,_):
                    return _resp_json(400, {'error': True,
                                            'message': "unknown or missing action; use 'ping', 'ping-mail', or 'grade'",
                                            'method':method,
                                            'path':path,
                                            'action':action })

        except Exception as e:  # pylint: disable=broad-exception-caught
            LOGGER.exception("Unhandled error")
            return _resp_json(500, {"error": True, "message": str(e)})

def _expire_batch(now:int, page: dict) -> int:
    n = 0
    for item in page.get("Items", []):
        if item.get("ttl", 0) <= now:
            sessions_table.delete_item(Key={"sid": item["sid"]})
            n += 1
    return n

def heartbeat_handler(event, context):
    """Called periodically"""
    LOGGER.info("heartbeat event=%s context=%s",event,context)
    now = int(time.time())
    expired = 0
    scan_kwargs = {"ProjectionExpression": "sid, ttl"}
    while True:
        page = sessions_table.scan(**scan_kwargs)
        expired += _expire_batch(now, page)
        if "LastEvaluatedKey" not in page:
            break
        scan_kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return {"statusCode": 200, "expired": expired}
