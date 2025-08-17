import json
import os
import time
from decimal import Decimal

import boto3
import paramiko

# Import shared runner from the package layer (vendor your e11core or zip it into the Lambda)
from e11.e11core.context import build_ctx
from e11.e11core.loader import discover_and_run

DDB_TABLE_ARN = os.environ["DDB_TABLE_ARN"]
SES_FROM = os.environ["SES_FROM"]
SSH_SECRET_ID = os.environ["SSH_SECRET_ID"]

_dynamo = boto3.client("dynamodb")
_ses = boto3.client("ses")
_secrets = boto3.client("secretsmanager")

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1]

def _send_email(to_addr, subject, body, cc=None):
    dest = {"ToAddresses": [to_addr]}
    if cc:
        dest["CcAddresses"] = [cc]
    _ses.send_email(
        Source=SES_FROM,
        Destination=dest,
        Message={"Subject": {"Data": subject}, "Body": {"Text": {"Data": body}}},
    )

def _put_result(email, lab, ip, dns, summary, meta):
    tbl = _ddb_table_name_from_arn(DDB_TABLE_ARN)
    item = {
        "email": {"S": email},
        "sk": {"S": f"run#{int(time.time())}"},
        "lab": {"S": lab},
        "ip": {"S": ip or ""},
        "dns": {"S": dns or ""},
        "score": {"N": str(summary["score"])},
        "pass_names": {"L": [{"S": n} for n in summary["passes"]]},
        "fail_names": {"L": [{"S": n} for n in summary["fails"]]},
        "raw": {"S": json.dumps(summary)[:35000]},
        "meta": {"S": json.dumps(meta)[:8000]},
    }
    _dynamo.put_item(TableName=tbl, Item=item)

def handler(event, _ctx):
    # Expected event: {"email": "...", "lab": "lab3", "public_ip": "...", "smashedemail": "..."}
    payload = event if isinstance(event, dict) else json.loads(event["body"])
    lab = payload["lab"]
    email = payload["email"]
    smashed = payload.get("smashedemail")
    ip = payload.get("public_ip")
    cc = payload.get("cc")

    # Build ctx and set grader mode
    os.environ["E11_MODE"] = "grader"
    ctx = build_ctx(lab)
    # Overwrite from payload if provided
    if smashed: ctx["smashedemail"] = smashed
    if ip: ctx["public_ip"] = ip

    # NEW: fetch SSH key and open the remote session
    secret = _secrets.get_secret_value(SecretId=SSH_SECRET_ID)
    key_pem = secret.get("SecretString") or secret["SecretBinary"]
    e11ssh.configure(host=ctx["public_ip"], username="ubuntu", port=22, pkey_pem=key_pem, timeout=10)
    e11ssh.set_working_dir(ctx["labdir"])

    try:
        summary = discover_and_run(ctx)
    finally:
        e11ssh.close()

    subject = f"[e11] {lab} score {summary['score']}/5.0"
    # Simple text mail body
    body_lines = [subject, "", "Passes:"]
    body_lines += [f"  ✔ {n}" for n in summary["passes"]]
    if summary["fails"]:
        body_lines += ["", "Failures:"]
        for t in summary["tests"]:
            if t["status"] == "fail":
                body_lines += [f"✘ {t['name']}: {t.get('message','')}"]
                if t.get("context"):
                    body_lines += ["-- context --", t["context"][:4000], ""]
    body = "\n".join(body_lines)

    _send_email(email, subject, body, cc=cc)
    _put_result(email, lab, ctx.get("public_ip"), ctx.get("labdns"), summary, {"lambda": "grader"})

    return {"statusCode": 200, "body": json.dumps({"ok": True, "score": summary["score"]})}
