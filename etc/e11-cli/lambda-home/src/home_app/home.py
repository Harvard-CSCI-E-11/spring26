"""
Main entry point for AWS Lambda Dashboard

Generate the https://csci-e-11.org/ home page.
Runs ODIC authentication for Harvard Key.
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
import time
import ipaddress
import datetime

from typing import Any, Dict, Tuple, Optional
from zoneinfo import ZoneInfo

import boto3
from boto3.dynamodb.conditions import Key

import paramiko.ssh_exception
from itsdangerous import BadSignature, SignatureExpired
import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound
from mypy_boto3_route53.type_defs import ChangeTypeDef, ChangeBatchTypeDef

from e11.e11core.e11ssh import E11Ssh
from e11.e11core.utils import smash_email
from e11.e11core import grader

from . import common
from . import oidc
from . import sessions

from .sessions import (
    new_session,
    get_session_from_event,
    all_sessions_for_email,
    delete_session_from_event,
)
from .sessions import get_user_from_email, delete_session, expire_batch
from .common import get_logger, add_user_log, EmailNotRegistered
from .common import users_table, sessions_table, SESSION_TTL_SECS, A
from .common import (
    route53_client,
    User,
    convert_dynamodb_item,
    make_cookie,
    get_cookie_domain,
    secretsmanager_client,
)
from .common import COURSE_DOMAIN, COOKIE_NAME


LOGGER = get_logger("home")
CSCIE_BOT = "cscie-bot"

__version__ = "0.1.0"
eastern = ZoneInfo("America/New_York")

LastEvaluatedKey = "LastEvaluatedKey"  # pylint: disable=invalid-name


def eastern_filter(value):
    """Format a time_t (epoch seconds) as ISO 8601 in EST5EDT."""
    if value in (None, jinja2.Undefined):  # catch both
        return ""
    try:
        dt = datetime.datetime.fromtimestamp(round(value), tz=eastern)
    except TypeError as e:
        LOGGER.debug("value=%s type(value)=%s e=%s", value, type(value), e)
        return "n/a"
    return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


# ---------- Setup AWS Services  ----------

# jinja2
env = Environment(
    loader=FileSystemLoader(
        ["templates", common.TEMPLATE_DIR, os.path.join(common.NESTED, "templates")]
    )
)
env.filters["eastern"] = eastern_filter

# Simple Email Service
SES_VERIFIED_EMAIL = "admin@csci-e-11.org"  # Verified SES email address
ses_client = boto3.client("ses")

# Route53 config for this course
HOSTED_ZONE_ID = "Z05034072HOMXYCK23BRA"  # from route53

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

################################################################
# Class constants
DOMAIN_SUFFIXES = ["", "-lab1", "-lab2", "-lab3", "-lab4", "-lab5", "-lab6", "-lab7"]
DASHBOARD = f"https://{COURSE_DOMAIN}"


def resp_json(
    status: int, body: Dict[str, Any], headers: Optional[Dict[str, str]] = None
) -> Dict[str, Any]:
    """End HTTP event processing with a JSON object"""
    LOGGER.debug("resp_json(status=%s) body=%s", status, body)
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            **(headers or {}),
        },
        "body": json.dumps(body),
    }


def resp_text(
    status: int,
    body: str,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """End HTTP event processing with text/html"""
    LOGGER.debug("resp_text(status=%s)", status)
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "text/html; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            **(headers or {}),
        },
        "body": body,
        "cookies": cookies or [],
    }


def resp_png(
    status: int,
    png_bytes: bytes,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[list[str]] = None,
) -> Dict[str, Any]:
    """End HTTP event processing with binary PNG"""
    LOGGER.debug("resp_png(status=%s, len=%s)", status, len(png_bytes))
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "image/png",
            "Access-Control-Allow-Origin": "*",
            **(headers or {}),
        },
        "body": base64.b64encode(png_bytes).decode("ascii"),
        "isBase64Encoded": True,
        "cookies": cookies or [],
    }


def redirect(
    location: str, extra_headers: Optional[dict] = None, cookies: Optional[list] = None
):
    """End HTTP event processing with redirect to another website"""
    LOGGER.debug("redirect(%s,%s,%s)", location, extra_headers, cookies)
    headers = {"Location": location}
    if extra_headers:
        headers.update(extra_headers)
    return {"statusCode": 302, "headers": headers, "cookies": cookies or [], "body": ""}


def error_404(page):
    """Generate an error"""
    template = env.get_template("404.html")
    return resp_text(404, template.render(page=page))


def static_file(fname):
    """Serve a static file"""
    if ("/" in fname) or (".." in fname) or ("\\" in fname):
        # path transversal attack?
        return error_404(fname)
    headers = {}
    try:
        if fname.endswith(".png"):
            with open(join(common.STATIC_DIR, fname), "rb") as f:
                return resp_png(200, f.read())

        with open(join(common.STATIC_DIR, fname), "r", encoding="utf-8") as f:
            if fname.endswith(".css"):
                headers["Content-Type"] = "text/css; charset=utf-8"
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


def all_logs_for_userid(user_id):
    """:param userid: The user to fetch logs for"""
    key_query = Key(A.USER_ID).eq(user_id) & Key(A.SK).begins_with(A.SK_LOG_PREFIX)
    logs = []
    resp = users_table.query(KeyConditionExpression=key_query)
    logs.extend(resp["Items"])
    while LastEvaluatedKey in resp:
        resp = users_table.query(
            KeyConditionExpression=key_query, ExclusiveStartKey=resp[LastEvaluatedKey]
        )
        logs.extend([User(**convert_dynamodb_item(u)) for u in resp["Items"]])
    return logs


################################################################
## http points


def do_page(event, status="", extra=""):
    """/ - generic page handler. page=? is optional page name.
    if no page is specified, give the login.html page, which invites the user to log in.
    """

    # get the query string
    qs = event.get("queryStringParameters") or {}
    page = qs.get("page")  # will be "foo" if URL is /?page=foo

    # Check for an active session. If it does not exist, redirect to the dashboard
    ses = get_session_from_event(event)

    if page:
        try:
            template = env.get_template(page)
            return resp_text(200, template.render(ses=ses, status=status, extra=extra))
        except TemplateNotFound:
            return error_404(page)

    # page not specified.
    # If there is a session, redirect to the /dashboard, otherwise give the login page.

    if ses:
        LOGGER.debug("ses=%s redirecting to /dashboard", ses)
        return redirect("/dashboard")

    # Build an authentication login
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(
        openid_config=oidc.get_oidc_config()
    )
    LOGGER.debug("url=%s issued_at=%s", url, issued_at)
    template = env.get_template("login.html")
    return resp_text(200, template.render(harvard_key=url, status=status, extra=extra))


def do_dashboard(event):
    """/dashboard
    If the session exists, then the user was created in new_session().
    """
    client_ip = event["requestContext"]["http"]["sourceIp"]
    ses = get_session_from_event(event)
    if not ses:
        return redirect("/")
    try:
        user = get_user_from_email(ses.email)
    except EmailNotRegistered:
        return resp_text(500, f"Internal error: no user for email address {ses.email}")

    # Get the dashboard items
    items = []
    resp = users_table.query(KeyConditionExpression=Key(A.USER_ID).eq(user.user_id))
    items.extend(resp["Items"])
    while LastEvaluatedKey in resp:
        resp = users_table.query(
            KeyConditionExpression=Key(A.USER_ID).eq(user.user_id),
            ExclusiveStartKey=resp[LastEvaluatedKey],
        )
        items.extend([User(**convert_dynamodb_item(u)) for u in resp["Items"]])

    logs = all_logs_for_userid(user.user_id)
    user_sessions = all_sessions_for_email(user.email)
    template = env.get_template("dashboard.html")
    return resp_text(
        200,
        template.render(
            user=user,
            ses=ses,
            client_ip=client_ip,
            sessions=user_sessions,
            logs=logs,
            items=items,
            now=round(time.time()),
        ),
    )


def oidc_callback(event):
    """OIDC callback from Harvard Key website."""
    params = event.get("queryStringParameters") or {}
    LOGGER.debug("callback params=%s", params)
    code = params.get("code")
    state = params.get("state")
    if not code:
        return {"statusCode": 400, "body": "Missing 'code' in query parameters"}
    try:
        obj = oidc.handle_oidc_redirect_stateless(
            openid_config=oidc.get_oidc_config(),
            callback_params={"code": code, "state": state},
        )
    except (SignatureExpired, BadSignature):
        return redirect("/expired")

    LOGGER.debug("obj=%s", obj)
    ses = new_session(event, obj["claims"])
    sid_cookie = make_cookie(
        COOKIE_NAME, ses.sid, max_age=SESSION_TTL_SECS, domain=get_cookie_domain(event)
    )
    LOGGER.debug("new_session sid=%s", ses.sid)
    return redirect("/dashboard", cookies=[sid_cookie])


def do_login(event):
    """/login?sid=<sid> - login and set the cookie"""
    qs = event.get("queryStringParameters") or {}
    sid = qs.get("sid")
    if not sid:
        return error_404("no session identifier provided")
    ses = sessions.get_session_from_sid(event, sid)
    if not ses:
        return error_404("no session found")
    sid_cookie = make_cookie(
        COOKIE_NAME, ses.sid, max_age=SESSION_TTL_SECS, domain=get_cookie_domain(event)
    )
    LOGGER.debug("creating cookie for /login link sid=%s", ses.sid)
    return redirect("/dashboard", cookies=[sid_cookie])


def do_logout(event):
    """/logout"""
    delete_session_from_event(event)
    del_cookie = make_cookie(
        COOKIE_NAME, "", clear=True, domain=get_cookie_domain(event)
    )
    (url, issued_at) = oidc.build_oidc_authorization_url_stateless(
        openid_config=oidc.get_oidc_config()
    )
    LOGGER.debug("url=%s issued_at=%s ", url, issued_at)
    return resp_text(
        200,
        env.get_template("logout.html").render(harvard_key=url),
        cookies=[del_cookie],
    )


def send_email(to_addr: str, email_subject: str, email_body: str):
    r = ses_client.send_email(
        Source=SES_VERIFIED_EMAIL,
        Destination={"ToAddresses": [to_addr]},
        Message={
            "Subject": {"Data": email_subject},
            "Body": {"Text": {"Data": email_body}},
        },
    )

    LOGGER.info(
        "send_email to=%s subject=%s SES response: %s", to_addr, email_subject, r
    )
    return r


################################################################
## api code.
## api calls do not use sessions. Authenticated APIs (e.g. api_register, api_grade)
## authenticate with api_authenticate(payload), which returns the user directory.


class APINotAuthenticated(Exception):
    def __init__(self, msg):
        super().__init__(msg)


def api_auth(payload):
    # See if there is an existing user_id for this email address.
    try:
        auth = payload["auth"]
    except KeyError as e:
        raise APINotAuthenticated("payload does not contain auth") from e

    email = auth.get(A.EMAIL, "")
    try:
        user = get_user_from_email(email)
    except EmailNotRegistered as e:
        raise APINotAuthenticated(
            f"User email {email} is not registered. Please visit {DASHBOARD} to register."
        ) from e

    # See if the user's course_key matches
    if user.course_key != auth.get(A.COURSE_KEY, ""):
        raise APINotAuthenticated(
            f"User course_key does not match registration course_key for email {email}. "
            f"Please visit {DASHBOARD} to find correct course_key."
        )
    return user


# pylint: disable=too-many-locals
def api_register(event, payload):
    """Register a VM"""
    LOGGER.info("api_register payload=%s event=%s", payload, event)
    if payload.get("auth", {}).get("email", "") != payload.get("registration", {}).get(
        "email", ""
    ):
        LOGGER.debug("*** auth.email != registration.email payload=%s", payload)
        return resp_json(403, {"message": "API auth.email != registration.email"})

    user = api_auth(payload)

    # Get the registration information
    registration = payload["registration"]
    email = registration.get("email")
    public_ip = registration.get("public_ip")
    instanceId = registration.get("instanceId")  # pylint: disable=invalid-name
    hostname = smash_email(email)

    # update the user record in table to match registration information
    users_table.update_item(
        Key={
            "user_id": user.user_id,
            "sk": user.sk,
        },
        UpdateExpression=f"SET {A.PUBLIC_IP} = :ip, {A.HOSTNAME} = :hn, {A.HOST_REGISTERED} = :t, {A.PREFERRED_NAME} = :preferred_name",
        ExpressionAttributeValues={
            ":ip": public_ip,
            ":hn": hostname,
            ":t": int(time.time()),
            ":preferred_name": registration.get(A.PREFERRED_NAME),
        },
    )
    add_user_log(
        event,
        user.user_id,
        f"User registered instanceId={instanceId} public_ip={public_ip}",
    )

    # Create DNS records in Route53
    hostnames = [f"{hostname}{suffix}.{COURSE_DOMAIN}" for suffix in DOMAIN_SUFFIXES]
    changes: list[ChangeTypeDef] = [
        ChangeTypeDef(
            Action="UPSERT",
            ResourceRecordSet={
                "Name": hostname,
                "Type": "A",
                "TTL": 300,
                "ResourceRecords": [{"Value": public_ip}],
            },
        )
        for hostname in hostnames
    ]

    change_batch = ChangeBatchTypeDef(Changes=changes)
    route53_response = route53_client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID, ChangeBatch=change_batch
    )
    LOGGER.info("Route53 response: %s", route53_response)
    for h in hostnames:
        add_user_log(event, user.user_id, f"DNS updated for {h}.{COURSE_DOMAIN}")

    # Send email notification using SES
    send_email(
        to_addr=email,
        email_subject=f"AWS Instance Registered. New DNS Record Created: {hostnames[0]}",
        email_body=EMAIL_BODY.format(
            hostname=hostnames[0],
            public_ip=public_ip,
            course_key=user.course_key,
            preferred_name=user.preferred_name,
        ),
    )
    add_user_log(event, user.user_id, f"Registration email sent to {email}")
    return resp_json(
        200, {"message": "DNS record created and email sent successfully."}
    )


def api_heartbeat(event, context):
    """Called periodically. Not authenticated. Main purpose is to remove expired sessions from database"""
    LOGGER.info("heartbeat event=%s context=%s", event, context)
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
    return resp_json(200, {"now": now, "expired": expired, "elapsed": time.time() - t0})


def get_pkey_pem(key_name):
    """Return the PEM key"""
    ssh_secret_id = os.environ.get("SSH_SECRET_ID", "please define SSH_SECRET_ID")
    secret = secretsmanager_client.get_secret_value(SecretId=ssh_secret_id)
    json_key = secret.get("SecretString")
    keys = json.loads(json_key)  # dictionary in the form of {key_name:value}
    try:
        return keys[key_name]
    except KeyError:
        LOGGER.error("keys  %s not found", key_name)
        raise


def api_grader(event, context, payload):
    """Get ready for grading, then run the grader."""
    LOGGER.info("do_grade event=%s context=%s payload=%s", event, context, payload)
    user = api_auth(payload)

    lab = payload["lab"]
    public_ip = user.public_ip
    email = user.email
    add_user_log(None, user.user_id, "Grading lab {lab} starts")
    summary = grader.grade_student_vm(
        user.email, user.public_ip, lab=lab, pkey_pem=get_pkey_pem(CSCIE_BOT)
    )
    add_user_log(None, user.user_id, "Grading lab {lab} ends")

    # Record grades
    now = datetime.datetime.now().isoformat()
    item = {
        A.USER_ID: user.user_id,
        A.SK: f"{A.SK_GRADE_PREFIX}{now}",
        A.LAB: lab,
        A.PUBLIC_IP: public_ip,
        "score": str(summary["score"]),
        "pass_names": summary["passes"],
        "fail_names": summary["fails"],
        "raw": json.dumps(summary)[:35000],
    }
    users_table.put_item(Item=item)
    LOGGER.info("DDB put_item to %s", users_table)

    # Send email
    (subject, body) = grader.create_email(summary)
    send_email(to_addr=email, email_subject=subject, email_body=body)

    return resp_json(200, {"summary": summary})


def api_check_access(event, payload, check_me=False):
    """Check to see if we can access the user's VM.
    Authentication requires knowing the user's email and the course_key.
    """
    if check_me is False:
        user = api_auth(payload)
        public_ip = str(user.public_ip)
        try:
            ipaddress.ip_address(public_ip)
        except ValueError as e:
            return resp_json(
                400,
                {
                    "error": "user.ipaddress is not valid",
                    "e": e,
                    "public_ip": public_ip,
                },
            )
        LOGGER.info("api_check_access user=%s public_ip=%s", user, public_ip)
    else:
        # Try to get the source IP
        public_ip = (
            event.get("requestContext", {}).get("identity", {}).get("sourceIp", None)
        )
        if public_ip is None:
            public_ip = (
                event.get("headers", {}).get("x-forwarded-for", ",").split(",")[0]
            )
        LOGGER.info("api_check_access check_me=True public_ip=%s", public_ip)

    ssh = E11Ssh(public_ip, pkey_pem=get_pkey_pem(CSCIE_BOT))

    try:
        rc, out, err = ssh.exec("hostname")
        return resp_json(
            200,
            {
                "error": False,
                "public_ip": public_ip,
                "message": f"Access On for IP address {public_ip}",
                "rc": rc,
                "out": out,
                "err": err,
            },
        )
    except paramiko.ssh_exception.AuthenticationException as e:
        return resp_json(
            200,
            {
                "error": False,
                "public_ip": public_ip,
                "message": f"Access Off for IP address {public_ip}",
                "e": str(e),
            },
        )


def api_delete_session(payload):
    """Delete the specified session. If the user knows the sid, that's good enough (we don't require that the sid be sealed)."""
    sid = payload.get("sid", "")
    if sid:
        return resp_json(200, {"result": delete_session(sid)})
    return resp_json(400, {"error": "no sid provided"})


################################################################
## Parse Lambda Events and cookies
# THis is the entry point
def parse_event(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """parser HTTP API v2 event"""
    stage = event.get("requestContext", {}).get("stage", "")
    path = event.get("rawPath") or event.get("path") or "/"
    if stage and path.startswith("/" + stage):
        path = path[len(stage) + 1 :] or "/"
    method = (
        event.get("requestContext", {})
        .get("http", {})
        .get("method", event.get("httpMethod", "GET"))
    )
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


################################################################
## main entry point from lambda system


# pylint: disable=too-many-return-statements, disable=too-many-branches, disable=unused-argument
def lambda_handler(event, context):
    """called by lambda"""
    method, path, payload = parse_event(event)

    # Detect if this is a browser request vs API request
    accept_header = event.get("headers", {}).get("accept", "")
    is_browser_request = "text/html" in accept_header
    with _with_request_log_level(payload):
        try:
            LOGGER.info(
                "req method='%s' path='%s' action='%s'",
                method,
                path,
                payload.get("action"),
            )
            action = (payload.get("action") or "").lower()

            match (method, path, action):
                ################################################################
                # Authentication callback
                #
                case ("GET", "/auth/callback", _):
                    return oidc_callback(event)

                ################################################################
                # JSON API Actions
                #
                case ("POST", "/api/v1", "ping"):
                    return resp_json(
                        200,
                        {
                            "error": False,
                            "message": "ok",
                            "path": sys.path,
                            "context": dict(context),
                            "environ": dict(os.environ),
                        },
                    )
                case ("POST", "/api/v1", "ping-mail"):
                    hostnames = ["first"]
                    public_ip = "<address>"
                    resp = send_email(
                        email_subject="E11 email ping",
                        email_body=EMAIL_BODY.format(
                            hostname=hostnames[0], public_ip=public_ip
                        ),
                        to_addr=payload[A.EMAIL],
                    )

                    return resp_json(
                        200,
                        {
                            "error": False,
                            "message": "ok",
                            "path": sys.path,
                            "resp": resp,
                            "environ": dict(os.environ),
                        },
                    )

                case ("POST", "/api/v1", "register"):
                    return api_register(event, payload)

                case ("POST", "/api/v1", "grade"):
                    return api_grader(event, context, payload)

                case ("POST", "/api/v1", "delete-session"):
                    return api_delete_session(payload)

                case ("POST", "/api/v1", "check-access"):
                    return api_check_access(event, payload, check_me=False)

                case ("POST", "/api/v1", "check-me"):
                    return api_check_access(event, payload, check_me=True)

                case ("POST", "/api/v1", "heartbeat"):
                    return api_heartbeat(event, context)

                # Must be last API call - match all actions
                case ("POST", "/api/v1", _):
                    return resp_json(
                        400,
                        {
                            "error": True,
                            "message": "unknown or missing action.",
                            "method": method,
                            "path": path,
                            "action": action,
                        },
                    )

                ################################################################
                # Human actions
                case ("GET", "/heartbeat", _):  # also called by lambda cron
                    return api_heartbeat(event, context)

                case ("GET", "/dashboard", _):
                    return do_dashboard(event)

                case ("GET", "/logout", _):
                    return do_logout(event)

                # note that / handles all pages. Specify html template with page= option
                case ("GET", "/", _):
                    return do_page(event)

                # This must be last - catch all GETs, check for /static
                # used for serving css and javascript
                case ("GET", p, _):
                    if p.startswith("/static"):
                        return static_file(p.removeprefix("/static/"))
                    return error_404(p)

                ################################################################
                # error
                case (_, _, _):
                    return error_404(path)

        except APINotAuthenticated as e:
            return resp_json(403, {"message": str(e)})

        except EmailNotRegistered as e:
            LOGGER.info("EmailNotRegistered: %s", e)

            if is_browser_request:
                template = env.get_template("error_user_not_registered.html")
                return resp_text(403, template.render())
            return resp_json(302, {"error": f"Email not registered {e}"})

        except Exception as e:  # pylint: disable=broad-exception-caught
            # Try to get session ID from cookies for better debugging
            session_id = "unknown"
            try:
                cookies = event.get("cookies", [])
                for cookie in cookies:
                    if cookie.startswith("AuthSid="):
                        session_id = cookie.split("=")[1]
                        break
            except Exception as ef:  # pylint: disable=broad-exception-caught
                LOGGER.exception("Unhandled innder exception. ef=%s", ef)
            LOGGER.exception("Unhandled exception! Session ID: %s  e=%s", session_id, e)

            if is_browser_request:
                # Return HTML error page for browser requests
                template = env.get_template("error_generic.html")
                return resp_text(
                    500, template.render(session_id=session_id, error_message=str(e))
                )
            # Return JSON for API requests
            return resp_json(
                500, {"error": True, "message": str(e), "session_id": session_id}
            )
