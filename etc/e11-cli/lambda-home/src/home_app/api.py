"""
API support for dashboard and SQS.

api calls do not use sessions. Authenticated APIs (e.g. api_register, api_grade)
authenticate with api_authenticate(payload), which returns the user directory.

"""

import os
import json
import sys
import time
import uuid
import ipaddress
from datetime import datetime
from typing import Any, Dict, Optional

from botocore.exceptions import ClientError
import paramiko.ssh_exception
from mypy_boto3_route53.type_defs import ChangeTypeDef, ChangeBatchTypeDef

from e11.e11core.utils import smash_email
from e11.e11core.e11ssh import E11Ssh
from e11.e11core import grader
from e11.e11_common import (
    A,
    EmailNotRegistered,
    add_grade,
    add_user_log,
    add_image,
    DASHBOARD,
    DNS_TTL,
    delete_image,
    route53_client,
    get_user_from_email,
    sessions_table,
    users_table,
    S3_BUCKET,
    s3_client,
    HOSTED_ZONE_ID,
    CSCIE_BOT,
    EMAIL_BODY,
    send_email,
    secretsmanager_client,
    LAB_CONFIG,
    LAB_TIMEZONE,
)
from e11.e11core.constants import (
    COURSE_DOMAIN,
    HTTP_OK,
    HTTP_BAD_REQUEST,
    HTTP_FORBIDDEN,
    HTTP_INTERNAL_ERROR,
    JSON_CONTENT_TYPE,
    JPEG_MIME_TYPE,
    CORS_HEADER,
    CORS_WILDCARD,
    CONTENT_TYPE_HEADER
)
from e11.e11core.utils import get_logger
from e11.main import __version__

from .sessions import (
    delete_session, expire_batch,
)



LOGGER = get_logger("home")

# Constants
DOMAIN_SUFFIXES = ['', '-lab1', '-lab2', '-lab3', '-lab4', '-lab5', '-lab6', '-lab7', '-lab8']
LastEvaluatedKey = "LastEvaluatedKey"  # pylint: disable=invalid-name

MAX_IMAGE_SIZE_BYTES = 10_000_000

def get_pkey_pem(key_name):
    """Return the PEM key"""
    try:
        ssh_secret_id = os.environ["SSH_SECRET_ID"]
    except KeyError as e:
        raise RuntimeError("SSH_SECRET_ID not defined") from e
    try:
        secret = secretsmanager_client.get_secret_value(SecretId=ssh_secret_id)
    except ClientError as e:
        LOGGER.exception("SecureId=%s", ssh_secret_id)
        raise RuntimeError("Unable to retrieve SSH secret from Secrets Manager") from e
    json_key = secret.get("SecretString")
    keys = json.loads(json_key)  # dictionary in the form of {key_name:value}
    try:
        return keys[key_name]
    except KeyError:
        LOGGER.exception("keys  %s not found. Available keys: %s", key_name, list(keys.keys()))
        raise

def make_presigned_post(bucket, key, email):
    """Return the S3 presigned_post fields"""
    return s3_client.generate_presigned_post(
        Bucket = bucket,
        Key = key,
        Conditions = [
            { "Content-Type": JPEG_MIME_TYPE },
            [ "content-length-range", 1, MAX_IMAGE_SIZE_BYTES],
            { "x-amz-meta-email": email}
        ],
        Fields = { "Content-Type": JPEG_MIME_TYPE,
                   "x-amz-meta-email" : email },
        ExpiresIn = 120 )

def make_presigned_url(bucket, key):
    """Return the S3 presigned URL"""
    return s3_client.generate_presigned_url(
        'get_object',
        Params={'Bucket':bucket, 'Key':key},
        ExpiresIn = 120)

class APINotAuthenticated(Exception):
    def __init__(self, msg):
        super().__init__(msg)

def resp_json( status: int, body: Dict[str, Any],
               headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """End HTTP event processing with a JSON object"""
    LOGGER.debug("resp_json(status=%s) body=%s", status, body)
    return {
        "statusCode": status,
        "headers": {
            CONTENT_TYPE_HEADER: JSON_CONTENT_TYPE,
            CORS_HEADER: CORS_WILDCARD,
            **(headers or {}),
        },
        "body": json.dumps(body, default=str),
    }


def validate_email_and_course_key(email, course_key):
    """validate an email address and course key. Return the user if successful, otherwise raise an exception."""
    try:
        user = get_user_from_email(email)
    except EmailNotRegistered as e:
        raise APINotAuthenticated( f"User email {email} is not registered. Please visit {DASHBOARD} to register." ) from e
    if user.course_key != course_key:
        raise APINotAuthenticated(
            f"User course_key does not match registration course_key for email {email}. "
            f"Please visit {DASHBOARD} to find correct course_key.")
    return user

def validate_payload(payload):
    # See if there is an existing user_id for this email address.
    LOGGER.info("validate_payload(%s)",payload)
    try:
        auth = payload["auth"]
    except KeyError as e:
        raise APINotAuthenticated("payload does not contain auth") from e
    return validate_email_and_course_key( auth.get(A.EMAIL, ""),
                                          auth.get(A.COURSE_KEY, ""))



###############################################################
# pylint: disable=too-many-locals
def api_register(event, payload):
    """Register a VM"""
    LOGGER.info("api_register payload=%s event=%s", payload, event)
    if payload.get("auth", {}).get("email", "") != payload.get("registration", {}).get(
        "email", ""
    ):
        LOGGER.debug("*** auth.email != registration.email payload=%s", payload)
        return resp_json(HTTP_FORBIDDEN, {"message": "API auth.email != registration.email"})

    user = validate_payload(payload)

    # Get the registration information
    verbose = payload.get('verbose',True)
    registration = payload['registration']
    email = registration.get('email')
    public_ip = registration.get('public_ip')
    instanceId = registration.get('instanceId') # pylint: disable=invalid-name
    hostname = smash_email(email)

    # update the user record in table to match registration information
    users_table.update_item( Key={ "user_id": user.user_id, "sk": user.sk, },
        UpdateExpression=f"SET {A.PUBLIC_IP} = :ip, {A.HOSTNAME} = :hn, {A.HOST_REGISTERED} = :t, {A.PREFERRED_NAME} = :preferred_name",
        ExpressionAttributeValues={
            ":ip": public_ip,
            ":hn": hostname,
            ":t": int(time.time()),
            ":preferred_name": registration.get(A.PREFERRED_NAME), } )

    add_user_log( event, user.user_id,
                  f"User registered instanceId={instanceId} public_ip={public_ip}")

    # Hosts that need to be created
    hostnames = [f"{hostname}{suffix}.{COURSE_DOMAIN}" for suffix in DOMAIN_SUFFIXES]

    #
    # Count records that will be changed or created
    #
    changed_records = 0
    new_records = 0
    for fqdn in hostnames:
        resp = route53_client.list_resource_record_sets(
            HostedZoneId=HOSTED_ZONE_ID,
            StartRecordName=fqdn,
            StartRecordType="A",
            MaxItems="1",
        )
        rrs = resp.get("ResourceRecordSets", [])
        match = next((r for r in rrs if r.get("Name", "").rstrip(".") == fqdn and r.get("Type") == "A"), None)
        if match:
            existing_vals = sorted(v["Value"] for v in match.get("ResourceRecords", []))
            if existing_vals != [public_ip]:
                changed_records += 1
        else:
            new_records += 1

    # Create DNS records in Route53
    changes: list[ChangeTypeDef] = [
        ChangeTypeDef( Action="UPSERT",
                       ResourceRecordSet={ "Name": hostname,
                                           "Type": "A",
                                           "TTL": DNS_TTL, "ResourceRecords": [{"Value": public_ip}]
                                          }
                      ) for hostname in hostnames ]

    change_batch = ChangeBatchTypeDef(Changes=changes)
    route53_response = route53_client.change_resource_record_sets(
        HostedZoneId=HOSTED_ZONE_ID, ChangeBatch=change_batch
    )
    LOGGER.info("Route53 response: %s", route53_response)
    for h in hostnames:
        add_user_log(event, user.user_id, f"DNS updated for {h}.{COURSE_DOMAIN}")

    # Send email notification using SES if there is a new record or a changed record
    if new_records > 0 or changed_records > 0 or verbose:
        subject_parts = []
        if new_records > 0:
            subject_parts.append(f"New DNS records created for {hostnames[0]}")
        if changed_records > 0:
            subject_parts.append(f"DNS records updated for {hostnames[0]}")
        subject = "CSCI E-11 Update: " + "; ".join(subject_parts) if subject_parts else "CSCI E-11 Update"
        send_email(to_addr=email,
                   email_subject = subject,
                   email_body = EMAIL_BODY.format(
                       hostname=hostnames[0],
                       public_ip=public_ip,
                       course_key=user.course_key,
                       preferred_name=user.preferred_name))
        add_user_log(event, user.user_id, f'Registration email sent to {email}')
        return resp_json(HTTP_OK,{'message':
                              'DNS updated and email sent successfully. '
                              f'new_records={new_records} changed_records={changed_records}'})
    return resp_json(HTTP_OK,{'message':f'DNS updated. No email sent. new_records={new_records} changed_records={changed_records}'})


def api_heartbeat(event, context):
    """Called periodically. Not authenticated. Main purpose is to remove expired sessions from database and keep lambda warm."""
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
    return resp_json(HTTP_OK, {"now": now, "expired": expired, "elapsed": time.time() - t0})

def api_grader(event, context, payload):
    """
    Get ready for grading, run the grader, store the results in the users table.
    sk format: "grade#lab2#time"

    Rejects grading requests if the lab deadline has passed, unless the request
    comes from SQS (which allows late grading for administrative purposes).
    """
    LOGGER.info("api_grader event=%s context=%s payload=%s",event,context,payload)
    user = validate_payload(payload)
    if user.email is None:
        LOGGER.error("user.email is None")
        return resp_json(HTTP_OK, {"error":True,
                                   "message":"user.email is None",
                                   "user":user})

    lab  = payload["lab"]
    note = payload.get("note")

    # Check if request is from SQS (allow late grading for SQS requests)
    is_sqs_request = event.get("source") == "sqs"

    # Check deadline unless this is an SQS request
    if not is_sqs_request:
        # Normalize lab name to "lab0", "lab1", etc.
        if lab.startswith("lab"):
            lab_key = lab
        else:
            # Extract number if lab is just a number or "lab0" format
            lab_num = lab.replace("lab", "").strip()
            lab_key = f"lab{lab_num}"

        if lab_key in LAB_CONFIG:
            deadline_str = LAB_CONFIG[lab_key]["deadline"]
            # Deadline is in Eastern time (no timezone in string)
            deadline = datetime.fromisoformat(deadline_str).replace(tzinfo=LAB_TIMEZONE)
            now = datetime.now(LAB_TIMEZONE)
            if now > deadline:
                LOGGER.warning("Grading request for %s rejected: deadline %s has passed (current time: %s)",
                             lab, deadline, now)
                return resp_json(HTTP_FORBIDDEN, {
                    "error": True,
                    "message": f"Lab {lab} deadline has passed. The deadline was {deadline_str}.",
                    "deadline": deadline_str
                })

    if user.public_ip is None:
        send_email(to_addr=user.email,
                   email_subject="Instance not registered",
                   email_body="Attempt to grade aborted, as your instance is not registered.")
        return resp_json(HTTP_OK, {"error":True,
                            "message":"Instance not registered",
                            "user":user })

    ###
    ### Here is where the actual grading happens...
    ###
    add_user_log(None, user.user_id, f"Grading lab {lab} starts", note=note)

    summary = grader.grade_student_vm( user.email, user.public_ip, lab=lab, pkey_pem=get_pkey_pem(CSCIE_BOT) )
    if summary['error']:
        LOGGER.error("summary=%s",summary)
        return resp_json(HTTP_INTERNAL_ERROR, summary)
    LOGGER.info("summary=%s",summary)

    add_user_log(None, user.user_id, f"Grading lab {lab} ends")
    add_grade(user, lab, user.public_ip, summary)

    # Send email
    (subject, body) = grader.create_email(summary, note)
    send_email(to_addr=user.email, email_subject=subject, email_body=body)
    return resp_json(HTTP_OK, {"summary": summary})


def api_check_access(event, payload, check_me=False):
    """Check to see if we can access the user's VM.
    Authentication requires knowing the user's email and the course_key.
    """
    if check_me is False:
        user = validate_payload(payload)
        public_ip = str(user.public_ip)
        try:
            ipaddress.ip_address(public_ip)
        except ValueError as e:
            return resp_json( HTTP_BAD_REQUEST, { "error": "user.ipaddress is not valid",
                                     "e": e,
                                     "public_ip": public_ip } )
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
        return resp_json( HTTP_OK, { "error": False,
                                 "public_ip": public_ip,
                                 "message": f"Access On for IP address {public_ip}",
                                 "rc": rc,
                                 "out": out,
                                 "err": err })
    except paramiko.ssh_exception.AuthenticationException as e:  # type: ignore[attr-defined]
        return resp_json( HTTP_OK, { "error": False,
                                 "public_ip": public_ip,
                                 "message": f"Access Off for IP address {public_ip}",
                                 "e": str(e) })

def api_delete_session(payload):
    """Delete the specified session. If the user knows the sid, that's good enough (we don't require that the sid be sealed)."""
    sid = payload.get("sid", "")
    if sid:
        return resp_json(HTTP_OK, {"result": delete_session(sid)})
    return resp_json(HTTP_BAD_REQUEST, {"error": "no sid provided"})

################ images ################
def api_post_image(event, payload):
    """For lab 8 - validate the course key and give the user an upload S3. The image only gets added to the database if there is a successful upload."""
    user = validate_payload( payload )
    s3key = "images/" + str(uuid.uuid4()) + ".jpeg"
    presigned_post = make_presigned_post(S3_BUCKET, s3key, user.email)
    LOGGER.info("event=%s payload=%s user=%s presigned_post=%s",event, payload, user,presigned_post)
    return resp_json(HTTP_OK, {"presigned_post":presigned_post})

def api_upload_callback(bucket, key):
    LOGGER.info("api_upload_callback(%s,%s)",bucket, key)
    # Get the metadata
    r = s3_client.head_object(Bucket=bucket, Key=key)
    email = r.get('Metadata',{}).get('email','')
    user = get_user_from_email(email) # email is already validated at this point (see above)
    add_image( user.user_id, 'lab8', bucket, key )

def api_delete_image(payload):
    """Delete the specified session. If the user knows the sid, that's good enough (we don't require that the sid be sealed)."""
    try:
        return resp_json(HTTP_OK, {"result": delete_image(payload.get("user_id"),
                                                          payload.get("sk"),
                                                          payload.get("bucket"),
                                                          payload.get("key"))})
    except (ValueError,TypeError,KeyError) as e:
        return resp_json(HTTP_BAD_REQUEST, {"error": str(e)})


# pylint: disable=too-many-positional-arguments,too-many-return-statements
def dispatch(method, action, event, context, payload):
    ################################################################
    # JSON API Actions
    #
    LOGGER.debug("dispatch(method=%s action=%s event=%s context=%s payload=%s",
                 method, action, event, context, payload)
    match (method, action):
        case ("POST", "ping"):
            return resp_json( HTTP_OK, {
                    "error": False,
                    "message": "ok",
                    "path": sys.path,
                    "context": dict(context),
                    "environ": dict(os.environ), }, )

        case ("POST", "ping-mail"):
            hostnames = ["first"]
            public_ip = "<address>"
            resp = send_email(
                email_subject="E11 email ping",
                email_body=EMAIL_BODY.format( hostname=hostnames[0], public_ip=public_ip ),
                to_addr=payload[A.EMAIL] )

            return resp_json( HTTP_OK, {
                "error": False,
                "message": "ok",
                "path": sys.path,
                "resp": resp,
                "environ": dict(os.environ),
                },)

        case ("POST", "register"):
            return api_register(event, payload)

        case ("POST", "grade"):
            return api_grader(event, context, payload)

        case ("POST", "delete-session"):
            return api_delete_session(payload)

        case ("POST", "delete-image"):
            return api_delete_image(payload)

        case ("POST", "check-access"):
            return api_check_access(event, payload, check_me=False)

        case ("POST", "check-me"):
            return api_check_access(event, payload, check_me=True)

        case ("POST", "post-image"):
            return api_post_image(event, payload)

        case ("POST", "heartbeat"):
            return api_heartbeat(event, context)

        case ("POST", "version"):
            return resp_json(HTTP_OK, {
                'error':False,
                'version':__version__,
                'deployment_timestamp':os.environ.get('DEPLOYMENT_TIMESTAMP')})

        # Must be last API call - match all actions
        case (_, _):
            return resp_json( HTTP_BAD_REQUEST,{
                "error": True,
                "message": "unknown or missing action.",
                "method": method,
                "action": action,
                "version": __version__ })
