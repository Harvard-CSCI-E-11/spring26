import base64
import json
import logging
import os
import time
import sys
from typing import Any, Dict, Tuple
from os.path import dirname

TASK_DIR = os.path.dirname(__file__)        # typically /var/task
NESTED = os.path.join(TASK_DIR, ".aws-sam", "build", "E11GraderFunction")
if not os.path.isdir(os.path.join(TASK_DIR, "e11")) and os.path.isdir(os.path.join(NESTED, "e11")):
    # put the nested dir first so `import e11` resolves
    sys.path.insert(0, NESTED)

import boto3

# ---------- logging setup ----------

LOGGER = logging.getLogger("e11.grader")
if not LOGGER.handlers:
    h = logging.StreamHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    LOGGER.addHandler(h)
try:
    LOGGER.setLevel(os.getenv("LOG_LEVEL", "INFO"))
except ValueError:
    LOGGER.setLevel(logging.INFO)


# ---------- clients / env ----------
_boto_ses = boto3.client("ses")
_boto_ddb = boto3.client("dynamodb")
_boto_secrets = boto3.client("secretsmanager")

DDB_TABLE_ARN = os.environ.get("DDB_TABLE_ARN")
SES_FROM = os.environ.get("SES_FROM")
SSH_SECRET_ID = os.environ.get("SSH_SECRET_ID")

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1] if arn and ":table/" in arn else arn

def _resp(status: int, body: Dict[str, Any], headers: Dict[str, str] = None) -> Dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*", **(headers or {})},
        "body": json.dumps(body),
    }

def _parse_event(event: Dict[str, Any]) -> Tuple[str, str, Dict[str, Any]]:
    # HTTP API v2
    path = event.get("rawPath") or event.get("path") or "/"
    method = event.get("requestContext", {}).get("http", {}).get("method", event.get("httpMethod", "GET"))
    body = event.get("body")
    if event.get("isBase64Encoded"):
        try:
            body = base64.b64decode(body or "").decode("utf-8", "replace")
        except Exception:
            body = None
    try:
        payload = json.loads(body) if body else {}
    except Exception:
        payload = {}
    return method, path, payload

def _with_request_log_level(payload: Dict[str, Any]):
    """Context manager to temporarily adjust log level from JSON (log_level or LOG_LEVEL)."""
    class _Ctx:
        def __enter__(self_):
            self_.old = LOGGER.level
            lvl = payload.get("log_level") or payload.get("LOG_LEVEL")
            if isinstance(lvl, str):
                LOGGER.setLevel(lvl)
            return self_
        def __exit__(self_, exc_type, exc, tb):
            LOGGER.setLevel(self_.old)
    return _Ctx()

def _send_email(to_addr: str, subject: str, body: str, cc: str = None):
    dest = {"ToAddresses": [to_addr]}
    if cc:
        dest["CcAddresses"] = [cc]
    _boto_ses.send_email(
        Source=SES_FROM,
        Destination=dest,
        Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
    )

def _grade(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Run grading by SSHing into the student's VM and executing tests via shared runner."""
    from e11.e11core.context import build_ctx
    from e11.e11core.loader import discover_and_run
    from e11.e11core import ssh as e11ssh

    email = payload.get("email")
    lab = payload.get("lab")
    smashed = payload.get("smashedemail")
    ip = payload.get("public_ip")
    cc = payload.get("cc")
    if not email or not lab or not ip:
        raise ValueError("grade requires fields: email, lab, public_ip")

    # Build context and mark grader mode
    os.environ["E11_MODE"] = "grader"
    ctx = build_ctx(lab)
    if smashed: ctx["smashedemail"] = smashed
    ctx["public_ip"] = ip  # ensure provided IP used

    # Open SSH (fetch key from Secrets Manager)
    secret = _boto_secrets.get_secret_value(SecretId=SSH_SECRET_ID)
    key_pem = secret.get("SecretString") or secret.get("SecretBinary")
    if isinstance(key_pem, bytes):
        key_pem = key_pem.decode("utf-8", "replace")

    LOGGER.info("SSH connect to %s (lab=%s)", ctx.get("public_ip"), lab)
    e11ssh.configure(host=ctx["public_ip"], username="ubuntu", port=22, pkey_pem=key_pem, timeout=10)
    e11ssh.set_working_dir(ctx["labdir"])

    try:
        summary = discover_and_run(ctx)
    finally:
        e11ssh.close()

    # Email summary
    subject = f"[e11] {lab} score {summary['score']}/5.0"
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

    LOGGER.info("SES email -> %s (cc=%s)", email, cc or "-")
    _send_email(email, subject, body, cc=cc)

    # Log to DDB
    tbl = _ddb_table_name_from_arn(DDB_TABLE_ARN)
    item = {
        "email": {"S": email},
        "sk": {"S": f"run#{int(time.time())}"},
        "lab": {"S": lab},
        "ip": {"S": ctx.get("public_ip") or ""},
        "dns": {"S": ctx.get("labdns") or ""},
        "score": {"N": str(summary["score"])},
        "pass_names": {"L": [{"S": n} for n in summary["passes"]]},
        "fail_names": {"L": [{"S": n} for n in summary["fails"]]},
        "raw": {"S": json.dumps(summary)[:35000]},
        "meta": {"S": json.dumps({"lambda": "grader"})[:8000]},
    }
    LOGGER.info("DDB put_item to %s", tbl)
    _boto_ddb.put_item(TableName=tbl, Item=item)

    return {"ok": True, "summary": summary}

def lambda_handler(event, context):
    method, path, payload = _parse_event(event)
    with _with_request_log_level(payload):
        try:
            LOGGER.info("req %s %s action=%s", method, path, payload.get("action"))
            action = (payload.get("action") or "").lower()

            match (method, path, action):
                case ("GET", "/", _):
                    return _resp(200, {"service": "e11-grader", "message": "send POST with JSON {'action':'grade'| 'ping' | 'ping-mail'}"})

                case (_, _, "ping"):
                    return _resp(200, {"error": False, "message": "ok", "path":sys.path})

                case (_, _, "ping-import"):
                    import e11
                    import e11.e11core
                    import e11.e11core.context
                    from e11.e11core.context import build_ctx
                    from e11.e11core.loader import discover_and_run
                    from e11.e11core import ssh as e11ssh

                    return _resp(200, {"error": False, "message": "ok", "path":sys.path})

                case (_, _,"ping-mail") if (email := payload.get("email")):
                    _send_email(email, "[e11] ping-mail", "Ping from e11 grader.")
                    return _resp(200, {"error": False, "message": f"sent to {email}"})

                case (_, _,"ping-mail"):
                    return _resp(400, {"error": True, "message": "email is required for ping-mail"})

                case (_, _, "grade"):
                    result = _grade(payload)
                    return _resp(200, result)

                case _:
                    return _resp(400, {"error": True, "message": "unknown or missing action; use 'ping', 'ping-mail', or 'grade'"})

        except Exception as e:
            LOGGER.exception("Unhandled error")
            return _resp(500, {"error": True, "message": str(e)})
