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
# at top of home_app/home.py (module import time)
import base64
import json
import os
from os.path import join
import sys
import binascii
import uuid
import time
import datetime

from typing import Any, Dict, Tuple, Optional
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key

from itsdangerous import BadSignature, SignatureExpired
import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from . import common
from . import oidc
from . import grader

from .common import get_logger,smash_email,add_user_log
from .common import users_table,sessions_table,SESSION_TTL_SECS,A
from .common import route53_client,secretsmanager_client, User, Session
from mypy_boto3_route53.type_defs import ChangeTypeDef, ChangeBatchTypeDef

LOGGER = get_logger("home")

__version__ = '0.1.0'
eastern = ZoneInfo("America/New_York")

def convert_dynamodb_item_to_user(item: dict) -> User:
    """Convert a DynamoDB item to a User object, handling type conversions."""
    converted_item = {}
    for key, value in item.items():
        # Convert numeric types to strings for Pydantic model compatibility
        if isinstance(value, (int, float)):
            converted_item[key] = str(value)
        else:
            converted_item[key] = value
    return User(**converted_item)

LastEvaluatedKey = 'LastEvaluatedKey' # pylint: disable=invalid-name

def eastern_filter(value):
    """Format a time_t (epoch seconds) as ISO 8601 in EST5EDT."""
    if value in (None, jinja2.Undefined):  # catch both
        return ""
    try:
        dt = datetime.datetime.fromtimestamp( round(value), tz=eastern)
    except TypeError as e:
        LOGGER.debug("value=%s type(value)=%s e=%s",value,type(value),e)
        return "n/a"
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")



# ---------- Setup AWS Services  ----------

# jinja2
env = Environment(loader=FileSystemLoader(["templates",common.TEMPLATE_DIR,os.path.join(common.NESTED,"templates")]))
env.filters["eastern"] = eastern_filter

# OIDC
OIDC_SECRET_ID = os.environ.get("OIDC_SECRET_ID","please define OIDC_SECRET_ID")

# SSH
SSH_SECRET_ID = os.environ.get("SSH_SECRET_ID","please define SSH_SECRET_ID")

# Auth Cookie
COOKIE_NAME = os.environ.get("COOKIE_NAME", "AuthSid")
COOKIE_SECURE = True
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN",'csci-e-11.org')
COOKIE_SAMESITE = os.environ.get("COOKIE_SAMESITE", "Lax")  # Lax|Strict|None

# Staging environment configuration
def is_staging_environment(event) -> bool:
    """Detect if we're running in the staging environment"""
    stage = event.get("requestContext", {}).get("stage", "")
    return stage == "stage"

def get_cookie_domain(event) -> str:
    """Get the appropriate cookie domain based on the environment"""
    if is_staging_environment(event):
        # In staging, always use the production domain for cookies
        # so sessions work across both environments
        return 'csci-e-11.org'
    return COOKIE_DOMAIN

class DatabaseInconsistency(RuntimeError):
    pass

class EmailNotRegistered(RuntimeError):
    pass

# Secrets Manager

# Simple Email Service
SES_VERIFIED_EMAIL = "admin@csci-e-11.org"      # Verified SES email address
ses_client = boto3.client("ses")

# Route53 config for this course
HOSTED_ZONE_ID = "Z05034072HOMXYCK23BRA"        # from route53

EMAIL_BODY="""
    You have successfully registered your AWS instance.

    Your course key is: {course_key}

    The following DNS record has been created:

    Hostname: {hostname}
    Public IP Address: {ipaddr}

    Best regards,
    CSCIE-11 Team
"""

################################################################
# Class constants
COURSE_KEY_LEN=6
DOMAIN='csci-e-11.org'
DOMAIN_SUFFIXES = ['', '-lab1', '-lab2', '-lab3', '-lab4', '-lab5', '-lab6', '-lab7']
DASHBOARD='https://csci-e-11.org'


def resp_json(status: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """End HTTP event processing with a JSON object"""
    LOGGER.debug("resp_json(status=%s)",status)
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": json.dumps(body),
    }

def resp_text(status: int, body: str, headers: Optional[Dict[str, str]] = None, cookies: Optional[list[str]] = None) -> Dict[str, Any]:
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

def error_404(page):
    """ Generate an error """
    template = env.get_template('404.html')
    return resp_text(404, template.render(page=page))

def static_file(fname):
    """ Serve a static file """
    headers = {}
    try:
        with open(join(common.STATIC_DIR,fname), "r", encoding='utf-8') as f:
            if fname.endswith('.css'):
                headers['Content-Type'] = 'text/css; charset=utf-8'
            return resp_text(200, f.read(), headers=headers)
    except FileNotFoundError:
        return error_404(fname)


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

def make_course_key():
    """Make a course key"""
    return str(uuid.uuid4())[0:COURSE_KEY_LEN]

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


def new_session(event, claims) -> Session:
    """Create a new session from the OIDC claims and store in the DyanmoDB table.
    The esid (email plus session identifier) is {email}:{uuid}
    Get the USER_ID from the users table. If it is not there, create it.
    Returns the Session object.
    """
    client_ip  = event["requestContext"]["http"]["sourceIp"]          # canonical client IP
    LOGGER.debug("in new_session. claims=%s client_ip=%s",claims,client_ip)
    email = claims[A.EMAIL]

    user = get_user_from_email(email)
    if user is None:
        now = int(time.time())
        user_id = str(uuid.uuid4())
        user = {A.USER_ID:user_id,
                A.SK:A.SK_USER,
                A.EMAIL:email,
                A.COURSE_KEY: make_course_key(),
                A.CREATED:now,
                A.CLAIMS:claims,
                A.UPDATED:now}
        ret = users_table.put_item(Item=user)        # USER CREATION POINT
        add_user_log(event, user_id, f"User {email} created", claims=claims)

    sid = str(uuid.uuid4())
    session = { "sid": sid,
             "email": email,
             A.SESSION_CREATED : int(time.time()),
             A.SESSION_EXPIRE  : int(time.time() + SESSION_TTL_SECS),
             "name" : claims.get('name',''),
             "client_ip": client_ip,
             "claims" : claims }
    ret = sessions_table.put_item(Item=session)
    LOGGER.debug("new_session table=%s user=%s session=%s ret=%s",sessions_table,user, session, ret)
    add_user_log(event, user_id, f"Session {sid} created")
    return Session(**session)

def get_session(event) -> Optional[Session]:
    """Return the session dictionary if the session is valid and not expired."""
    sid = parse_cookies(event).get(COOKIE_NAME)
    LOGGER.debug("get_session sid=%s get_cookie_domain(%s)=%s",sid,event,get_cookie_domain(event))
    if not sid:
        return None
    resp = sessions_table.get_item(Key={"sid":sid})
    LOGGER.debug("get_session sid=%s resp=%s",sid,resp)
    item = resp.get('Item')
    if item is None:
        return None
    ses = Session(**item)
    now  = int(time.time())
    if not ses:
        LOGGER.debug("get_session no ses")
        return None
    if ses.session_expire <= now:
        # Session has expired. Delete it and return none
        LOGGER.debug("Deleting expired sid=%s session_expire=%s now=%s",sid,ses.session_expire,now)
        sessions_table.delete_item(Key={"sid":sid})
        add_user_log(event, "unknown", f"Session {sid} expired")
        return None
    LOGGER.debug("get_session session=%s",ses)
    return ses

def all_logs_for_userid(user_id):
    """:param userid: The user to fetch logs for"""
    key_query = Key(A.USER_ID).eq(user_id) & Key(A.SK).begins_with(A.SK_LOG_PREFIX)
    logs = []
    resp = users_table.query( KeyConditionExpression=key_query    )
    logs.extend(resp['Items'])
    while LastEvaluatedKey in resp:
        resp = users_table.query( KeyConditionExpression=key_query,
                                  ExclusiveStartKey=resp[LastEvaluatedKey])
        logs.extend([convert_dynamodb_item_to_user(u) for u in resp['Items']])
    return logs


def all_sessions_for_email(email):
    """Return all of the sessions for an email address"""
    resp = sessions_table.query(
        IndexName="GSI_Email",
        KeyConditionExpression="email = :e",
        ExpressionAttributeValues={":e":email},
    )
    sessions = resp["Items"]
    return sessions

def delete_session_from_event(event):
    """Delete the session, whether it exists or not"""
    sid = parse_cookies(event).get(COOKIE_NAME)
    if not sid:
        return
    sessions_table.delete_item(Key={"sid":sid})

################################################################
## http points

def do_page(event, status="",extra=""):
    """/ - generic page handler. page=? is optional page name.
    if no page is specified, give the login.html page, which invites the user to log in.
    """

    # get the query string
    qs = event.get("queryStringParameters") or {}
    page = qs.get("page")   # will be "foo" if URL is /?page=foo

    # If there is an active session, redirect to the dashboard
    ses = get_session(event)

    if page:
        try:
            template = env.get_template(page)
            return resp_text(200, template.render(ses=ses, status=status, extra=extra))
        except TemplateNotFound:
            return error_404(page)

    # page not specified.
    # If there is a session, redirect to the /dashboard, otherwise give the login page.

    if ses:
        LOGGER.debug("ses=%s redirecting to /dashboard",ses)
        return redirect("/dashboard")

    # Build an authentication login
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.debug("url=%s issued_at=%s",url,issued_at)
    template = env.get_template("login.html")
    return resp_text(200, template.render(harvard_key=url, status=status, extra=extra))

def do_dashboard(event):
    """/dashboard
    If the session exists, then the user was created in new_session().
    """
    client_ip = event["requestContext"]["http"]["sourceIp"]
    ses = get_session(event)
    if not ses:
        return redirect("/")
    try:
        user = get_user_from_email(ses.email)
    except EmailNotRegistered:
        return resp_text(500, f"Internal error: no user for email address {ses.email}")

    # Get the dashboard items
    items = []
    resp = users_table.query( KeyConditionExpression=Key(A.USER_ID).eq(user.user_id) )
    items.extend(resp['Items'])
    while LastEvaluatedKey in resp:
        resp = users_table.query( KeyConditionExpression=Key(A.USER_ID).eq(user.user_id),
                                  ExclusiveStartKey=resp[LastEvaluatedKey])
        items.extend([convert_dynamodb_item_to_user(u) for u in resp['Items']])

    logs = all_logs_for_userid(user.user_id)
    sessions = all_sessions_for_email(user.email)
    template = env.get_template("dashboard.html")
    return resp_text(200, template.render(user=user,
                                          ses=ses,
                                          client_ip=client_ip,
                                          sessions=sessions,
                                          logs=logs,
                                          items=items,
                                          ses_dump=json.dumps(ses,default=str,indent=4),
                                          now=round(time.time())))

def do_callback(event):
    """OIDC callback from Harvard Key website.
    """
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
    ses = new_session(event,obj['claims'])
    sid_cookie = make_cookie(COOKIE_NAME, ses.sid, max_age=SESSION_TTL_SECS, domain=get_cookie_domain(event))
    LOGGER.debug("new_session sid=%s",ses.sid)
    return redirect("/dashboard", cookies=[sid_cookie])

def do_logout(event):
    """/logout"""
    delete_session_from_event(event)
    del_cookie = make_cookie(COOKIE_NAME, "", clear=True, domain=get_cookie_domain(event))
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
    LOGGER.debug("url=%s issued_at=%s ",url,issued_at)
    return resp_text(200, env.get_template("logout.html").render(harvard_key=url), cookies=[del_cookie])

def get_user_from_email(email) -> User:
    """Given an email address, get the user record from the users_table.
    Note - when the first session is created, we don't know the user-id.
    """
    resp = users_table.query(IndexName="GSI_Email", KeyConditionExpression=Key("email").eq(email))
    if resp['Count']>1:
        raise DatabaseInconsistency(f"multiple database entries with the same email: {resp}")
    if resp['Count']==1:
        raise EmailNotRegistered(email)
    item = resp['Items'][0]
    return convert_dynamodb_item_to_user(item)

def send_email(to_addr: str, email_subject: str, email_body: str, cc: Optional[str] = None):
    r = ses_client.send_email(
        Source=SES_VERIFIED_EMAIL,
        Destination={'ToAddresses': [to_addr]},
        Message={ 'Subject': {'Data': email_subject},
                  'Body': {'Text': {'Data': email_body}} } )

    LOGGER.info("send_email to=%s subject=%s SES response: %s",to_addr,email_subject,r)
    return r


# pylint: disable=too-many-locals
def do_register(event,payload):
    """Register a VM"""
    LOGGER.info("do_register payload=%s event=%s",payload,event)
    registration = payload['registration']
    email = registration.get(A.EMAIL)
    ipaddr = registration.get('ipaddr')
    instanceId = registration.get('instanceId') # pylint: disable=invalid-name
    hostname = smash_email(email)

    # See if there is an existing user_id for this email address.
    try:
        user = get_user_from_email(email)
    except EmailNotRegistered:
        return resp_json(403, {'message':'User email not registered. Please visit {DASHBOARD} to register.',
                               A.EMAIL:email})

    # See if the user's course_key matches
    if user.course_key != registration.get('course_key'):
        return resp_json(403,
                         {'message':
                          'User course_key does not match registration course_key. '
                          'Please visit {DASHBOARD} to find correct course_key.',
                          A.EMAIL:email})

    # update the user record
    users_table.update_item( Key={ "user_id": user.user_id,
                                   "sk": user.sk,
                                  },
                             UpdateExpression=f"SET {A.IPADDR} = :ip, {A.HOSTNAME} = :hn, {A.REG_TIME} = :t, {A.NAME} = :name",
                             ExpressionAttributeValues={
                                 ":ip": ipaddr,
                                 ":hn": hostname,
                                 ":t": int(time.time()),
                                 ":name": registration.get('name')
        }
    )
    add_user_log(event, user.user_id, f'User registered instanceId={instanceId} ipaddr={ipaddr}')

    # Create DNS records in Route53
    hostnames = [f"{hostname}{suffix}.{DOMAIN}" for suffix in DOMAIN_SUFFIXES]
    changes: list[ChangeTypeDef] = [
        ChangeTypeDef(
            Action="UPSERT",
            ResourceRecordSet={
                "Name": hostname,
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": ipaddr}]
            }
        )
        for hostname in hostnames
    ]

    change_batch = ChangeBatchTypeDef(Changes=changes)
    route53_response = route53_client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID,
        ChangeBatch=change_batch
    )
    LOGGER.info("Route53 response: %s",route53_response)
    for h in hostnames:
        add_user_log(event, user.user_id, f'DNS updated for {h}.{DOMAIN}')

    # Send email notification using SES
    send_email(to_addr=email,
               email_subject = f"AWS Instance Registered. New DNS Record Created: {hostnames[0]}",
               email_body = EMAIL_BODY.format(hostname=hostnames[0], ipaddr=ipaddr, course_key=user.course_key))
    add_user_log(event, user.user_id, f'Registration email sent to {email}')
    return resp_json(200,{'message':'DNS record created and email sent successfully.'})




################################################################
def expire_batch(now:int, items: list) -> int:
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
    scan_kwargs: dict[str, Any] = {"ProjectionExpression": "sid, session_expire"}
    while True:
        page = sessions_table.scan(**scan_kwargs)
        expired += expire_batch(now, page.get("Items", []))
        if LastEvaluatedKey not in page:
            break
        scan_kwargs["ExclusiveStartKey"] = page[LastEvaluatedKey]
    return resp_json(200, {"now":now, "expired": expired, "elapsed" : time.time() - t0})

def do_grader(event, context, payload):
    """Get ready for grading, then run the grader."""
    LOGGER.info("do_grade event=%s context=%s",event,context)
    ses = get_session(event)
    if not ses:
        return resp_json(400, {'message':'No session cookie.','error':True})

    user = get_user_from_email(ses.email)

    # Open SSH (fetch key from Secrets Manager)
    secret = secretsmanager_client.get_secret_value(SecretId=SSH_SECRET_ID)
    key_pem = secret.get("SecretString") or secret.get("SecretBinary")
    if isinstance(key_pem, bytes):
        key_pem = key_pem.decode("utf-8", "replace")

    lab = payload['lab']
    ipaddr = user.ipaddr
    email = user.email
    summary = grader.grade_student_vm(user=user,lab=lab,key_pem=key_pem)

    # Create email message for user
    subject = f"[E11] {lab} score {summary['score']}/5.0"
    body_lines = [subject, "", "Passes:"]
    body_lines += [f"  ✔ {n}" for n in summary["passes"]]
    if summary["fails"]:
        body_lines += ["", "Failures:"]
        for t in summary["tests"]:
            if t["status"] == "fail":
                body_lines += [f"✘ {t['name']}: {t.get('message','')}"]
                if t.get("context"):
                    body_lines += ["-- context --", (t["context"][:4000] or ""), ""]
    body = "\n".join(body_lines)

    send_email(to_addr = email,
               email_subject=subject,
               email_body = body)

    now = datetime.datetime.now().isoformat()
    item = { A.USER_ID: user.user_id,
             A.SK: f"{A.SK_GRADE_PREFIX}{now}",
             A.LAB: lab,
             A.IPADDR: ipaddr,
             "score": str(summary["score"]),
             "pass_names": summary["passes"],
             "fail_names": summary["fails"],
             "raw": json.dumps(summary)[:35000]}
    users_table.put_item(Item=item)
    LOGGER.info("DDB put_item to %s", users_table)

    return resp_json(200, {'summary':summary})


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
                # Authentication callback
                #
                case ("GET","/auth/callback",_):
                    return do_callback(event)

                ################################################################
                # JSON Actions
                #
                case ("POST", "/api/v1", "ping"):
                    return resp_json(200, {"error": False, "message": "ok", "path":sys.path,
                                           'context':dict(context),
                                           'environ':dict(os.environ)
                                           })

                case ("POST", "/api/v1", "ping-mail"):
                    hostnames = ['first']
                    ipaddr = '<address>'
                    resp = send_email(email_subject = "E11 email ping",
                               email_body = EMAIL_BODY.format(hostname=hostnames[0], ipaddr=ipaddr),
                               to_addr=payload[A.EMAIL])

                    return resp_json(200, {"error": False, "message": "ok",
                                           "path":sys.path,
                                           "resp":resp,
                                           'environ':dict(os.environ)})

                case ("POST", "/api/v1", "register"):
                    return do_register(event, payload)

                case ("POST", '/api/v1', 'heartbeat'):
                    return do_heartbeat(event, context)

                case ("POST", '/api/v1', 'grade'):
                    return do_grader(event, context, payload)

                case ("POST", "/api/v1", _):
                    return resp_json(400, {'error': True,
                                            'message': "unknown or missing action.",
                                            'method':method,
                                            'path':path,
                                            'action':action })

                case ("GET", "/heartbeat", _):
                    return do_heartbeat(event, context)


                ################################################################
                # Human actions
                case ("GET","/", _):
                    return do_page(event)

                case ("GET","/dashboard",_):
                    return do_dashboard(event)

                case ("GET","/logout",_):
                    return do_logout(event)

                # This must be last - catch all GETs, check for /static
                case ("GET", p, _):
                    if p.startswith("/static"):
                        return static_file(p.removeprefix("/static/"))
                    return error_404(p)

                ################################################################
                # error
                case (_,_,_):
                    return error_404(path)

        except Exception as e:  # pylint: disable=broad-exception-caught
            LOGGER.exception("Unhandled exception!")
            return resp_json(500, {"error": True, "message": str(e)})
