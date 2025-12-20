"""
Main entry point for AWS Lambda Dashboard

Generate the https://csci-e-11.org/ home page.
Runs ODIC authentication for Harvard Key.
Supports logging in and logging out.
Allows users to see all active sessions and results of running the grader.

Data Model:
Users table:
PK: user_id
SK determines if we are storing user record or the log#, grade#, image#,
See e11_common.py for details

Sessions table:
PK: session_id

Cookies - just have sid (session ID). If you know it, you are authenticated (they are hard to guess)
"""

# at top of home_app/home.py (module import time)
import base64
import json
import os
from os.path import join
import binascii
import time
import datetime

from typing import Any, Dict, Tuple, Optional
from zoneinfo import ZoneInfo

from boto3.dynamodb.conditions import Key

from itsdangerous import BadSignature, SignatureExpired
import jinja2
from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from e11.e11_common import (
    A,
    EmailNotRegistered,
    User,
    convert_dynamodb_item,
    users_table,
    queryscan_table,
    SES_VERIFIED_EMAIL,
    ses_client,
    GITHUB_REPO_URL,
    LAB_REDIRECTS
)

from e11.e11core.constants import (
    API_PATH,
    HTTP_OK,
    HTTP_FOUND,
    HTTP_BAD_REQUEST,
    HTTP_FORBIDDEN,
    HTTP_NOT_FOUND,
    HTTP_INTERNAL_ERROR,
    HTML_CONTENT_TYPE,
    PNG_CONTENT_TYPE,
    CSS_CONTENT_TYPE,
    CORS_HEADER,
    CORS_WILDCARD,
    CONTENT_TYPE_HEADER
)
from e11.main import __version__
from e11.e11core.utils import get_logger

from . import oidc
from . import sessions
from . import api
from .api import resp_json, make_presigned_url

from .sqs_support import (
    is_sqs_event,
    handle_sqs_event,
    sqs_send_signed_message,
)

from .sessions import (
    get_user_from_email, new_session,
    get_session_from_event,
    all_sessions_for_email,
    delete_session_from_event,
)

from .common import (
    make_cookie,
    get_cookie_domain,
    COOKIE_NAME,
    SESSION_TTL_SECS,
    TEMPLATE_DIR,
    STATIC_DIR,
    NESTED
    )


LOGGER = get_logger("home")

def send_email(to_addr: str, email_subject: str, email_body: str):
    r = ses_client.send_email(
        Source=SES_VERIFIED_EMAIL,
        Destination={"ToAddresses": [to_addr]},
        Message={
            "Subject": {"Data": email_subject},
            "Body": {"Text": {"Data": email_body}},
        },
    )
    LOGGER.info("send_email to=%s subject=%s SES response: %s", to_addr, email_subject, r)
    return r


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

# jinja2 environment for template substitution
env = Environment(
    loader=FileSystemLoader(
        ["templates", TEMPLATE_DIR, os.path.join(NESTED, "templates")]
    )
)
env.globals["API_PATH"] = API_PATH
env.filters["eastern"] = eastern_filter
env.globals["GITHUB_REPO_URL"] = GITHUB_REPO_URL

# Route53 config for this course (imported from e11_common)

DOMAIN_SUFFIXES = ['', '-lab1', '-lab2', '-lab3', '-lab4', '-lab5', '-lab6', '-lab7', '-lab8']


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
            CONTENT_TYPE_HEADER: HTML_CONTENT_TYPE,
            CORS_HEADER: CORS_WILDCARD,
            **(headers or {}),
        },
        "body": body,
        "cookies": cookies or [],
    }


def resp_png(
    status: int,
    png_bytes: bytes,
    headers: Optional[Dict[str, str]] = None,
    cookies: Optional[list[str]] = None ) -> Dict[str, Any]:
    """End HTTP event processing with binary PNG"""
    LOGGER.debug("resp_png(status=%s, len=%s)", status, len(png_bytes))
    return {
        "statusCode": status,
        "headers": {
            CONTENT_TYPE_HEADER: PNG_CONTENT_TYPE,
            CORS_HEADER: CORS_WILDCARD,
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
    return {"statusCode": HTTP_FOUND, "headers": headers, "cookies": cookies or [], "body": ""}


def error_404(page):
    """Generate an error"""
    template = env.get_template("404.html")
    return resp_text(HTTP_NOT_FOUND, template.render(page=page))


def static_file(fname):
    """Serve a static file"""
    if ("/" in fname) or (".." in fname) or ("\\" in fname):
        # path transversal attack?
        return error_404(fname)
    headers = {}
    try:
        if fname.endswith(".png"):
            with open(join(STATIC_DIR, fname), "rb") as f:
                return resp_png(HTTP_OK, f.read())

        with open(join(STATIC_DIR, fname), "r", encoding="utf-8") as f:
            if fname.endswith(".css"):
                headers[CONTENT_TYPE_HEADER] = CSS_CONTENT_TYPE
            return resp_text(HTTP_OK, f.read(), headers=headers)
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
    kwargs = {'KeyConditionExpression':Key(A.USER_ID).eq(user_id) & Key(A.SK).begins_with(A.SK_LOG_PREFIX)}
    logs = queryscan_table(users_table.query, kwargs)
    logs = [User(**convert_dynamodb_item(u)) for u in logs]
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
            return resp_text(HTTP_OK, template.render(ses=ses, status=status, extra=extra))
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
    return resp_text(HTTP_OK, template.render(harvard_key=url, status=status, extra=extra))


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
        return resp_text(HTTP_INTERNAL_ERROR, f"Internal error: no user for email address {ses.email}")

    # Get the dashboard items --- everything from DynamoDB for this user_id

    # This is faster than separately getting the logs, the grades, the images, etc...
    kwargs = {'KeyConditionExpression':Key(A.USER_ID).eq(user.user_id)}
    items = queryscan_table(users_table.query, kwargs)

    # Convert to a User object. Additional records are kept
    # items = [User(**convert_dynamodb_item(u)) for u in items]

    # Extract out the data
    logs   = [item for item in items if item[A.SK].startswith(A.SK_LOG_PREFIX)]
    grades = [item for item in items if item[A.SK].startswith(A.SK_GRADE_PREFIX)]
    images = [item for item in items if item[A.SK].startswith(A.SK_IMAGE_PREFIX)]

    # sign the image URLs
    for image in images:
        image['url'] = make_presigned_url(image[A.BUCKET], image[A.KEY])

    user_sessions = all_sessions_for_email(user.email)
    template = env.get_template("dashboard.html")
    return resp_text( HTTP_OK,
                      template.render(
                          user=user,
                          ses=ses,
                          client_ip=client_ip,
                          sessions=user_sessions,
                          logs=logs,
                          grades=grades,
                          images = images,
                          now=round(time.time()) ) )




def oidc_callback(event):
    """OIDC callback from Harvard Key website."""
    params = event.get("queryStringParameters") or {}
    LOGGER.debug("callback params=%s", params)
    code = params.get("code")
    state = params.get("state")
    if not code:
        return {"statusCode": HTTP_BAD_REQUEST, "body": "Missing 'code' in query parameters"}
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
        HTTP_OK,
        env.get_template("logout.html").render(harvard_key=url),
        cookies=[del_cookie],
    )


def queue_grade(email: str, lab: str) -> Dict[str, Any]:
    """
    Queue a grading request for a student's lab via SQS.

    Args:
        email: Student email address
        lab: Lab name (e.g., 'lab0', 'lab1')

    Returns:
        SQS send_message response (includes MessageId)

    Raises:
        EmailNotRegistered: If the email is not registered
    """
    # Get the user to retrieve their course_key for authentication
    user = get_user_from_email(email)

    # Create the payload that api_grader expects
    payload = {
        "auth": {
            A.EMAIL: user.email,
            A.COURSE_KEY: user.course_key,
        },
        "lab": lab,
    }

    # Send the signed message to SQS
    LOGGER.info("Queueing grade request for email=%s lab=%s", email, lab)
    result = sqs_send_signed_message(action="grade", method="POST", payload=payload)
    LOGGER.info("Queued grade request MessageId=%s", result.get("MessageId"))
    return result


################################################################
## api code.
## api calls do not use sessions. Authenticated APIs (e.g. api_register, api_grade)
## authenticate with api_authenticate(payload), which returns the user directory.


################################################################
## Parse Lambda Events and cookies
# This is the entry point
# pylint: disable=too-many-locals
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

def parse_s3_event(event):
    if event.get('source','')=='aws.s3' and event.get('detail-type','')=='Object Created':
        detail = event.get('detail',{})

        request_id = detail.get('request-id','')

        bucket = detail.get('bucket',{}).get('name')
        key = detail.get('object',{}).get('key')
        if (bucket is None) or (key is None):
            LOGGER.error("bucket=%s key=%s event=%s",bucket,key,event)
            return resp_json(200, {"error":True, 'bucket':bucket, 'key':key}) # 200 so we do not get retried
        return request_id, bucket, key
    return None, None, None

################################################################
## main entry point from lambda system

def safe_dump_environment():
    for k,v in sorted(os.environ.items()):
        if k in ('AWS_SECRET_ACCESS_KEY','AWS_SESSION_TOKEN'):
            v = '********'
        print(f"{k} = {v}")


# pylint: disable=too-many-return-statements, disable=too-many-branches, disable=unused-argument
def lambda_handler(event, context):
    """called by lambda.
    break out the HTTP method, the HTTP path, and the JSON body as a payload.
    """

    # Check for upload
    request_id, bucket, key = parse_s3_event(event)
    if bucket is not None:
        LOGGER.info("request_id=%s",request_id)         # Make sure this is not a duplicate request?
        return api.api_upload_callback(bucket, key)

    # Check for sqs
    if is_sqs_event(event):
        return handle_sqs_event(event, context)

    # regular HTTP
    method, path, payload = parse_event(event)

    # Detect if this is a browser request vs API request
    accept_header = event.get("headers", {}).get("accept", "")
    is_browser_request = "text/html" in accept_header

    # Extract source IP address
    source_ip = (
        event.get("requestContext", {}).get("http", {}).get("sourceIp")
        or event.get("requestContext", {}).get("identity", {}).get("sourceIp")
        or event.get("headers", {}).get("x-forwarded-for", "").split(",")[0].strip()
        or "unknown"
    )

    with _with_request_log_level(payload):
        try:
            LOGGER.info(
                "req method='%s' path='%s' action='%s' source_ip='%s'",
                method,
                path,
                payload.get("action"),
                source_ip,
            )
            action = (payload.get("action") or "").lower()

            if path == API_PATH:
                return api.dispatch(method, action, event, context, payload)
            ################################################################
            # Non-API routes
            #
            match (method, path):
                ################################################################
                # Authentication callback
                #
                case ("GET", "/auth/callback"):
                    return oidc_callback(event)

                ################################################################
                # Human actions
                case ("GET", "/heartbeat"):  # also called by lambda cron
                    return api.api_heartbeat(event, context)

                case ("GET", "/dashboard"):
                    return do_dashboard(event)

                case ("GET", "/logout"):
                    return do_logout(event)

                # note that / handles all pages. Specify html template with page= option
                case ("GET", "/"):
                    return do_page(event)

                # lab redirects
                case ("GET", "/lab0"):
                    return redirect(LAB_REDIRECTS[0])
                case ("GET", "/lab1"):
                    return redirect(LAB_REDIRECTS[1])
                case ("GET", "/lab2"):
                    return redirect(LAB_REDIRECTS[2])
                case ("GET", "/lab3"):
                    return redirect(LAB_REDIRECTS[3])
                case ("GET", "/lab4"):
                    return redirect(LAB_REDIRECTS[4])
                case ("GET", "/lab5"):
                    return redirect(LAB_REDIRECTS[5])
                case ("GET", "/lab6"):
                    return redirect(LAB_REDIRECTS[6])
                case ("GET", "/lab7"):
                    return redirect(LAB_REDIRECTS[7])
                case ("GET", "/lab8"):
                    return redirect(LAB_REDIRECTS[8])

                case ("GET", "/version"):
                    return resp_text(HTTP_OK, f"version: {__version__} of {os.environ.get('DEPLOYMENT_TIMESTAMP')}\n")

                # This must be last - catch all GETs, check for /static
                # used for serving css and javascript
                case ("GET", p):
                    if p.startswith("/static"):
                        return static_file(p.removeprefix("/static/"))
                    return error_404(p)

                ################################################################
                # error
                case (_, _):
                    return error_404(path)

        except api.APINotAuthenticated as e:
            return resp_json(HTTP_FORBIDDEN, {"message": str(e)})

        except EmailNotRegistered as e:
            LOGGER.info("EmailNotRegistered: %s", e)

            if is_browser_request:
                template = env.get_template("error_user_not_registered.html")
                return resp_text(HTTP_FORBIDDEN, template.render())
            return resp_json(HTTP_FORBIDDEN, {"error": f"Email not registered {e}"})

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
                LOGGER.exception("Unhandled inner exception. ef=%s", ef)
            LOGGER.exception("Unhandled exception! Session ID: %s  e=%s", session_id, e)

            if is_browser_request:
                # Return HTML error page for browser requests
                template = env.get_template("error_generic.html")
                return resp_text(
                    HTTP_INTERNAL_ERROR, template.render(session_id=session_id, error_message=str(e))
                )
            # Return JSON for API requests
            return resp_json(
                HTTP_INTERNAL_ERROR, {"error": True, "message": str(e), "session_id": session_id}
            )
