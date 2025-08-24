"""
Generate the https://csci-e-11.org/ home page.
Runs OIDC authentication for Harvard Key.
Supports logging in and logging out.
Allows users to see all active sessions and results of running the grader.
"""

import base64
import json
import os
import sys
import binascii
import uuid
import time
from typing import Any, Dict, Tuple, Optional
#from os.path import dirname

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
SESSION_TTL_SECS = int(os.environ.get("SESSION_TTL_SECS", str(60*60*24*180)))  # 180 days

#_boto_ses = boto3.client("ses")
_boto_ddb = boto3.client("dynamodb")
_boto_secrets = boto3.client("secretsmanager")

env = Environment(loader=FileSystemLoader(["templates",common.TEMPLATE_DIR,os.path.join(common.NESTED,"templates")]))

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1] if arn and ":table/" in arn else arn

dynamodb_resource = boto3.resource( 'dynamodb', region_name=DDB_REGION ) # our dynamoDB is in region us-east-1
table = dynamodb_resource.Table(_ddb_table_name_from_arn(DDB_TABLE_ARN))

def _resp_json(status: int, body: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": json.dumps(body),
    }

def _resp_text(status: int, body: str, headers: Dict[str, str] = None, cookies: Dict[str, str]=None) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": body,
        "cookies": cookies or [],
    }

def _redirect(location:str, extra_headers: Optional[dict] = None, cookies: Optional[list]=None):
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
    session_id = str(uuid.uuid4())
    table.put_item(Item={ "email": email, # primary key
                          "sk": f"session#{session_id}", # secondary key
                          "time" : int(time.time()),
                          "ttl"  : int(time.time()) + SESSION_TTL_SECS,
                          "name" : claims['name'],
                          "client_ip": client_ip or "",
                          "claims" : claims })
    return f"{email}:{session_id}"

def get_session(event) -> Optional[dict]:
    """Return the session dictionary if the session is valid and not expired."""
    esid = parse_cookies(event).get(COOKIE_NAME)
    try:
        (email,session_id) = esid.split(":")
    except (ValueError,AttributeError):
        LOGGER.warning("esid=%s",esid)
        return None             # did not unpack properly
    key = {"email":email, "sk": f"session#{session_id}"}
    resp = table.get_item(Key=key)
    item = resp.get("Item")
    now  = int(time.time())
    if not item:
        return None
    if item.get("ttl", 0) <= now:
        # Session has expired. Delete it and return none
        LOGGER.info("Deleting expired key %s ttl=%s now=%s",key,item.get("ttl",0),now)
        table.delete_item(Key=key)
        return None
    return item

def delete_session(event):
    """Delete the session, whether it exists or not"""
    esid = parse_cookies(event).get(COOKIE_NAME)
    try:
        (email,session_id) = esid.split(":")
    except (ValueError,AttributeError):
        LOGGER.warning("esid=%s",esid)
        return
    key = {"email":email, "sk": f"session#{session_id}"}
    table.delete_item(Key=key)

################################################################
## http points

def do_home_page(event, context, status="",extra=""):  # pylint: disable=unused_argument
    """/"""
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.info("url=%s issued_at=%s",url,issued_at)
    template = env.get_template("index.html")
    return _resp_text(200, template.render(harvard_key=url, status=status, extra=extra))

def do_dashboard(event, context): # pylint: disable=unused_argument
    """/dashboard"""
    ses = get_session(event)
    template = env.get_template("dashboard.html")
    # TODO: Get all activate sessions and allow them to be deleted
    # TODO: Get all all activity
    return _resp_text(200, template.render())


def do_callback(event,context): # pylint: disable=unused_argument
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

def do_logout(event, context):# pylint: disable=unused_argument
    """/logout"""
    delete_session(event)
    del_cookie = make_cookie(COOKIE_NAME, "", clear=True)
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.info("url=%s issued_at=%s ",url,issued_at)
    return _resp_text(200, env.get_template("logout.html").render(harvard_key=url), cookies=[del_cookie])


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
                case ("GET", "/", "ping"):
                    return _resp_json(200, {"error": False, "message": "ok", "path":sys.path, 'environ':os.environ})

                case ("GET","/", _):
                    return do_home_page(event,context)

                case ("GET","/auth/callback",_):
                    return do_callback(event,context)

                case ("GET","/dashboard",_):
                    return do_dashboard(event, context)

                case ("GET","/logout",_):
                    return do_logout(event, context)

                case (_,_,_):
                    return _resp_json(400, {'error': True,
                                       'message': "unknown or missing action; use 'ping', 'ping-mail', or 'grade'",
                                       'method':method,
                                       'path':path,
                                       'action':action })

        except Exception as e:  # pylint: disable=broad-exception-caught
            LOGGER.exception("Unhandled error")
            return _resp_json(500, {"error": True, "message": str(e)})
