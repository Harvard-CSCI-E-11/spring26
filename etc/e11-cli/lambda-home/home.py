"""
Generate the https://csci-e-11.org/ home page.
"""

import base64
import json
import logging
import os
import sys
import binascii
import uuid
from typing import Any, Dict, Tuple
from os.path import dirname

import boto3

TASK_DIR = os.path.dirname(__file__)
NESTED = os.path.join(TASK_DIR, ".aws-sam", "build", "E11HomeFunction")
if not os.path.isdir(os.path.join(TASK_DIR, "e11")) and os.path.isdir(os.path.join(NESTED, "e11")):
    sys.path.insert(0, NESTED)
sys.path.append(TASK_DIR)


import oidc                     # pylint: disable=wrong-import-position
# ---------- logging setup ----------
from constants import LOGGER

# ---------- clients / env ----------
_boto_ses = boto3.client("ses")
_boto_ddb = boto3.client("dynamodb")
_boto_secrets = boto3.client("secretsmanager")
OIDC_SECRET_ID = os.environ.get("OIDC_SECRET_ID")

DDB_TABLE_ARN = os.environ.get("DDB_TABLE_ARN")

INDEX_PAGE = os.path.join( dirname(__file__), 'static', 'index.html')

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1] if arn and ":table/" in arn else arn

def _resp(status: int, body: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": json.dumps(body),
    }

def _textresp(status: int, body: str, headers: Dict[str, str] = None) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "text/html; charset=utf-8", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": body,
    }

def _parse_event(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    """ parser HTTP API v2 event"""
    path = event.get("rawPath") or event.get("path") or "/"
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

def get_odic_config():
    """Return the config from AWS Secrets"""
    harvard_secrets = json.loads(_boto_secrets.get_secret_value(SecretId=OIDC_SECRET_ID)['SecretString'])
    LOGGER.info("type(harvard_secrets)=%s",type(harvard_secrets))
    LOGGER.info("secret keys: %s",list(harvard_secrets.keys()))
    config = oidc.load_openid_config(harvard_secrets['oidc_discovery_endpoint'],
                                     client_id=harvard_secrets['client_id'],
                                     redirect_uri=harvard_secrets['redirect_uri'])
    return {**config,**harvard_secrets}

def register_action(claims,client_ip):
    tbl = _ddb_table_name_from_arn(DDB_TABLE_ARN)
    item = {
        "email": {"S": claims['email']},
        "sk": {"S": f"run#{int(time.time())}"},
        "name" : {"S" : claims['_name']},
        "token" : {"S" : str(uuid.uuid4())},
        "client_ip": {"S": ipaddr or ""},
    }
    dynamodb.put_item(TableName=tbl, Item=item)
    return _textresp(200, f"<html><body><p>Here is what the SAML claims look like:</p><pre>\n{json.dumps(ret,indent=4)}\n</pre>\n</body></html>\n")


def home_page(status=""):
    with open(INDEX_PAGE,"r") as f:# pylint: disable=unspecified-encoding
        (url, issued_at) = oidc.build_oidc_authorization_url_stateless(openid_config = get_odic_config())
        LOGGER.info("url=%s issued_at=%s",url,issued_at)
        body = f.read()
        body = body.replace("{{key}}", url).replace("{{status}}",status)
        return _textresp(200, body)


# pylint: disable=too-many-return-statements
def lambda_handler(event, context): # pylint: disable=unused-argument
    """called by lambda"""
    method, path, payload = _parse_event(event)
    with _with_request_log_level(payload):
        try:
            LOGGER.info("req method='%s' path='%s' action='%s'", method, path, payload.get("action"))
            action = (payload.get("action") or "").lower()

            match (method, path, action):
                case ("GET","/prod/", _):
                    return home_page()

                case ("GET","/prod/auth/callback",_):
                    params = event.get("queryStringParameters") or {}
                    LOGGER.info("callback params=%s",params)
                    code = params.get("code")
                    state = params.get("state")
                    if not code:
                        return {
                            "statusCode": 400,
                            "body": "Missing 'code' in query parameters"
                        }
                    try:
                        obj = oidc.handle_oidc_redirect_stateless(openid_config = get_odic_config(),
                                                                  callback_params={'code':code,'state':state})
                    except oidc.OidcExpired:
                        return home_page("state expired")

                    LOGGER.info("obj=%s",obj)
                    client_ip  = event["requestContext"]["http"]["sourceIp"]          # canonical client IP
                    return register_action(obj['claims'],client_ip=client_ip)

                case ("GET", "/", _):
                    return _resp(200, {"service": "e11-grader", "message": "send POST with JSON {'action':'grade'| 'ping' | 'ping-mail'}"})

                case (_, _, "ping"):
                    return _resp(200, {"error": False, "message": "ok", "path":sys.path, 'environ':os.environ})

                case _:
                    return _resp(400, {'error': True,
                                       'message': "unknown or missing action; use 'ping', 'ping-mail', or 'grade'",
                                       'method':method,
                                       'path':path,
                                       'action':action })

        except Exception as e:  # pylint: disable=broad-exception-caught
            LOGGER.exception("Unhandled error")
            return _resp(500, {"error": True, "message": str(e)})
