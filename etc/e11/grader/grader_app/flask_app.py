"""
Leaerboard Fask Application (src/app.py).
"""
import time
import os
import logging
import base64

from flask import Flask, request, jsonify, render_template, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from botocore.exceptions import ClientError
import boto3
from itsdangerous import Serializer,BadSignature,BadData

# Import shared runner from the package layer (vendor your e11core or zip it into the Lambda)
from e11.e11core.context import build_ctx
from e11.e11core.loader import discover_and_run

__version__ = '1.0.0'

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
INACTIVE_SECONDS = 120
DEFAULT_GRADER_TABLE = 'Grader'

dynamodb = boto3.resource( 'dynamodb')
grader_table = dynamodb.Table(os.environ.get('GRADER_TABLE', DEFAULT_GRADER_TABLE))

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.logger.setLevel(logging.DEBUG)

DDB_TABLE_ARN = os.environ["DDB_TABLE_ARN"]
SES_FROM = os.environ["SES_FROM"]
SSH_SECRET_ID = os.environ["SSH_SECRET_ID"]

dynamodb = boto3.client("dynamodb")
ses = boto3.client("ses")
secrets = boto3.client("secretsmanager")

def _ddb_table_name_from_arn(arn: str) -> str:
    return arn.split(":table/")[-1]

def _send_email(to_addr, subject, body, cc=None):
    dest = {"ToAddresses": [to_addr]}
    if cc:
        dest["CcAddresses"] = [cc]
    ses.send_email(
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
    dynamodb.put_item(TableName=tbl, Item=item)

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
    secret = secrets.get_secret_value(SecretId=SSH_SECRET_ID)
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

@app.route('/ver', methods=['GET'])
def app_ver():
    return __version__

@app.route('/')
def root():
    """Return the grader page"""
    # Read and encode the icon
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
    with open(icon_path, 'rb') as f:
        icon_data = base64.b64encode(f.read()).decode('utf-8')

    # Get the IP address
    if request.headers.get('X-Forwarded-For'):
        ip_address = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip_address = request.remote_addr

    return render_template('grader.html',
                         ip_address=ip_address,
                         FAVICO=icon_data)

@app.route('/api/grade', methods=['POST'])
def api_grade():   # pylint disable=missing-function-docstring
    # and return to the caller
    return jsonify({'error':True,'message':'Not implemented yet.'})
