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
import re
from typing import Any, Dict, Tuple, Optional

import boto3
from boto3.dynamodb.conditions import Key

from itsdangerous import BadSignature, SignatureExpired
from jinja2 import Environment,FileSystemLoader

from . import common
from . import oidc
from .common import LOGGER

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1] if arn and ":table/" in arn else arn

# ---------- Setup AWS Services  ----------

# jinja2
env = Environment(loader=FileSystemLoader(["templates",common.TEMPLATE_DIR,os.path.join(common.NESTED,"templates")]))

# OIDC
OIDC_SECRET_ID = os.environ.get("OIDC_SECRET_ID")

# DynamoDB
DDB_REGION = os.environ.get("DDB_REGION","us-east-1")
DDB_USERS_TABLE_ARN = os.environ.get("DDB_USERS_TABLE_ARN","e11-users")
SESSIONS_TABLE_NAME = os.environ.get("SESSIONS_TABLE_NAME","e11-sessions")
SESSION_TTL_SECS    = int(os.environ.get("SESSION_TTL_SECS", str(60*60*24*180)))  # 180 days
dynamodb_client = boto3.client("dynamodb")
dynamodb_resource = boto3.resource( 'dynamodb', region_name=DDB_REGION ) # our dynamoDB is in region us-east-1
users_table    = dynamodb_resource.Table(_ddb_table_name_from_arn(DDB_USERS_TABLE_ARN))
sessions_table = dynamodb_resource.Table(SESSIONS_TABLE_NAME)

# Auth Cookie
COOKIE_NAME = os.environ.get("COOKIE_NAME", "AuthSid")
COOKIE_SECURE = True
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN",'csci-e-11.org')
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")  # Lax|Strict|None

# Secrets Manager
secretsmanager_client = boto3.client("secretsmanager")

# Simple Email Service
SES_VERIFIED_EMAIL = "admin@csci-e-11.org"      # Verified SES email address
ses_client = boto3.client("ses")

# Route53 config for this course
HOSTED_ZONE_ID = "Z05034072HOMXYCK23BRA"        # from route53
DOMAIN='csci-e-11.org'
DOMAIN_SUFFIXES = ['', '-lab1', '-lab2', '-lab3', '-lab4', '-lab5', '-lab6', '-lab7']
route53_client = boto3.client('route53')

EMAIL_BODY="""
    You have successfully registered your AWS instance.

    Your course key is: {course_key}

    The following DNS record has been created:

    Hostname: {hostname}
    IP Address: {ip_address}

    Best regards,
    CSCIE-11 Team
"""



def resp_json(status: int, body: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
    """End HTTP event processing with a JSON object"""
    LOGGER.debug("resp_json(status=%s)",status)
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": json.dumps(body),
    }

def resp_text(status: int, body: str, headers: Dict[str, str] = None, cookies: Dict[str, str]=None) -> Dict[str, Any]:
    """End HTTP event processing with text/html"""
    LOGGER.debug("resp_text(status=%s)",status)
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": body,
        "cookies": cookies or [],
    }

def redirect(location:str, extra_headers: Optional[dict] = None, cookies: Optional[list]=None):
    """End HTTP event processing with redirect to another website"""
    LOGGER.debug("redirect(%s,%s,%s)",location,extra_headers,cookies)
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
    harvard_secrets = json.loads(secretsmanager_client.get_secret_value(SecretId=OIDC_SECRET_ID)['SecretString'])
    LOGGER.debug("fetched secret %s keys: %s",OIDC_SECRET_ID,list(harvard_secrets.keys()))
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
    item = { "sid": sid,
             "email": email,
             "time" : int(time.time()),
             "session_expire"  : int(time.time()) + SESSION_TTL_SECS,
             "name" : claims.get('name',''),
             "client_ip": client_ip or "",
             "claims" : claims }
    ret = sessions_table.put_item(Item=item)
    LOGGER.debug("new_session ret=%s item=%s",ret,item)
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
    if item.get("session_expire", 0) <= now:
        # Session has expired. Delete it and return none
        LOGGER.debug("Deleting expired sid=%s session_expire=%s now=%s",sid,item.get("session_expire",0),now)
        sessions_table.delete_item(Key={"sid":sid})
        return None
    LOGGER.debug("session=%s",item)
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
        return redirect("/dashboard")
    # Build an authentication login
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.debug("url=%s issued_at=%s",url,issued_at)
    template = env.get_template("index.html")
    return resp_text(200, template.render(harvard_key=url, status=status, extra=extra))

def do_dashboard(event):
    """/dashboard"""
    ses = get_session(event)
    if not ses:
        LOGGER.debug("No session; redirect to /")
        return redirect("/")
    user_id = ses['user_id']

    # Get the dashboard items
    items = []
    resp = users_table.query( KeyConditionExpression=Key('user_id').eq(user_id) )
    items.extend(resp['Items'])
    while 'LastEvaluatedKey' in resp:
        resp = users_table.query( KeyConditionExpression=Key('user_id').eq(user_id),
        ExclusiveStartKey=resp['LastEvaluatedKey'] )
    items.extend(resp['Items'])
    # See if we can find the user item
    users = [item for item in items if item['sk']=='#']
    if users:
        user = users[0]
    else:
        user = {'course_key':'error',
                'email':'error - no email',
                'hostname':'error - no hostname',
                'ip_address':'0.0.0.0',
                'name':'error - no # sk',
                'time':0 }

    sessions = all_sessions_for_email(user['email'])

    template = env.get_template("dashboard.html")
    return resp_text(200, template.render(user=user, sessions=sessions, items=items))

def do_callback(event):
    """OIDC callback from Harvard Key website."""
    params = event.get("queryStringParameters") or {}
    LOGGER.debug("callback params=%s",params)
    code = params.get("code")
    state = params.get("state")
    if not code:
        return { "statusCode": 400,
                 "body": "Missing 'code' in query parameters" }
    try:
        obj = oidc.handle_oidc_redirect_stateless(openid_config = get_odic_config(),
                                                  callback_params={'code':code,'state':state})
    except (SignatureExpired,BadSignature):
        return redirect("/expired")

    LOGGER.debug("obj=%s",obj)
    client_ip  = event["requestContext"]["http"]["sourceIp"]          # canonical client IP
    sid = new_session(obj['claims'],client_ip=client_ip)
    sid_cookie = make_cookie(COOKIE_NAME, sid, max_age=SESSION_TTL_SECS, domain=COOKIE_DOMAIN)
    return redirect("/dashboard", cookies=[sid_cookie])

def do_logout(event):
    """/logout"""
    delete_session(event)
    del_cookie = make_cookie(COOKIE_NAME, "", clear=True)
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.debug("url=%s issued_at=%s ",url,issued_at)
    return resp_text(200, env.get_template("logout.html").render(harvard_key=url), cookies=[del_cookie])

def smash_email(email):
    """Convert an email into the CSCI E-11 smashed email"""
    email    = re.sub(r'[^-a-zA-Z0-9_@.+]', '', email).lower().strip()
    smashed_email = "".join(email.replace("@",".").split(".")[0:2])
    return smashed_email

# pylint: disable=too-many-locals
def do_register(payload,event):
    """Register a VM"""
    LOGGER.info("do_register payload=%s event=%s",payload,event)
    registration = payload['registration']
    email = registration['email']
    ipaddr = registration['ipaddr']
    hostname = smash_email(email)

    # Create DNS records in Route53
    changes = []
    hostnames = [f"{hostname}{suffix}.{DOMAIN}" for suffix in DOMAIN_SUFFIXES]
    changes   = [{ "Action": "UPSERT",
                         "ResourceRecordSet": {
                             "Name": hostname,
                             "Type": "A",
                             "TTL": 300,
                             "ResourceRecords": [{"Value": ipaddr}]
                             }}
                 for hostname in hostnames]

    route53_response = route53_client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch={
            "Changes": changes
        })
    LOGGER.info("Route53 response: %s",route53_response)

    # See if there is an existing user_id for this email address.
    resp = users_table.get_item(Key={'user_id':'bogus','sk':'#'})
    resp = users_table.query(IndexName="GSI_Email", KeyConditionExpression=Key("email").eq(email))
    if resp['Count']>1:
        return resp_json(400, {'message':"multiple database entries with the same email: {resp}"})
    if resp['Count']==1:
        # User already exist.
        user_id    = resp['Items'][0]['user_id']
        course_key = resp['Items'][0]['course_key']
    else:
        # Create new user_id and course key
        user_id = str(uuid.uuid4()) # user_id is a uuid
        course_key = resp.get('Item',{}).get('course_key', str(uuid.uuid4())[0:8])

    # store the new student_dict
    new_student_dict = {'user_id':user_id, # primary key
                        'sk':"#",          # sort key - '#' is the student record
                        'email':email,
                        'course_key':course_key,
                        'time':int(time.time()),
                        'name':registration['name'],
                        'ip_address':ipaddr,
                        'hostname':hostname}
    users_table.put_item(Item=new_student_dict)

    # Send email notification using SES
    email_subject = f"AWS Instance Registered. New DNS Record Created: {hostnames[0]}"
    email_body = EMAIL_BODY.format(hostname=hostnames[0], ip_address=ipaddr, course_key=course_key)
    ses_response = ses_client.send_email(
        Source=SES_VERIFIED_EMAIL,
        Destination={'ToAddresses': [email]},
        Message={ 'Subject': {'Data': email_subject},
                  'Body': {'Text': {'Data': email_body}} } )
    LOGGER.info("SES response: %s",ses_response)

    return resp_json(200,{'message':'DNS record created and email sent successfully.'})


def do_grade(event):
    """Do a grade"""
    LOGGER.info("do_register event=%s",event)
    return resp_json(400, {'error':True})

################################################################
def expire_batch(now:int, items: dict) -> int:
    """Actually delete the items"""
    n = 0
    for item in items:
        if item.get("session_expire", 0) <= now:
            sessions_table.delete_item(Key={"sid": item["sid"]})
            n += 1
    return n

def do_heartbeat(event, context):
    """Called periodically"""
    LOGGER.info("heartbeat event=%s context=%s",event,context)
    t0 = time.time()
    now = int(time.time())
    expired = 0
    scan_kwargs = {"ProjectionExpression": "sid, session_expire"}
    while True:
        page = sessions_table.scan(**scan_kwargs)
        expired += expire_batch(now, page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        scan_kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return resp_json(200, {"now":now, "expired": expired, "elapsed" : time.time() - t0})

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
                ################################################################
                # JSON Actions
                case ("POST", "/", "ping"):
                    return resp_json(200, {"error": False, "message": "ok", "path":sys.path, 'environ':dict(os.environ)})

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

                    return resp_json(200, {"error": False, "message": "ok", "path":sys.path, 'environ':dict(os.environ)})

                case ("POST", "/register", "register"):
                    return do_register(payload, event)

                case ("GET", "/heartbeat", _):
                    return do_heartbeat(event, context)

                ################################################################
                # Human actions
                case ("GET","/", _):
                    return do_home_page(event)

                case ("GET","/auth/callback",_):
                    return do_callback(event)

                case ("GET","/dashboard",_):
                    return do_dashboard(event)

                case ("GET","/logout",_):
                    return do_logout(event)

                ################################################################
                # error
                case (_,_,_):
                    return resp_json(400, {'error': True,
                                            'message': "unknown or missing action; use 'ping', 'ping-mail', or 'grade'",
                                            'method':method,
                                            'path':path,
                                            'action':action })

        except Exception as e:  # pylint: disable=broad-exception-caught
            LOGGER.exception("Unhandled error")
            return resp_json(500, {"error": True, "message": str(e)})
