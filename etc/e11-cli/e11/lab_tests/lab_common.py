"""
lab_common.py: common things for the lab tester.
"""

from uuid import uuid4
import time
import urllib
import urllib.parse
import json
import mimetypes
import re
import yaml
import yaml.scanner

from e11.e11core.utils import get_logger
from e11.e11core.decorators import retry, timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail,assert_contains

CONFIG_FILE = "/home/ubuntu/e11-config.ini"
AUTO_GRADER_KEY_LINE = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIEK/6zvwwWOO+ui4zbUYN558g+LKh5N8f3KpoyKKrmoR "
    "auto-grader-do-not-delete"
)
UPLOAD_TIMEOUT_SECONDS = 10

logger = get_logger()

def make_multipart_body(fields: dict[str, str], file_field: str, file_name:str, file_bytes:bytes) -> tuple[bytes, str]:
    """
    fields: regular form fields (name -> value)
    file_field: form field name for the file (e.g., "file" or "image")
    file_name: name for upload
    file_bytes: the data itself

    Returns (body_bytes, content_type_header_value)
    """
    boundary = f"----PythonFormBoundary{uuid4().hex}"
    boundary_bytes = boundary.encode("ascii")
    crlf = b"\r\n"

    parts: list[bytes] = []

    # Text fields
    for name, value in fields.items():
        parts.append(b"--" + boundary_bytes + crlf)
        header = f'Content-Disposition: form-data; name="{name}"'.encode("utf-8")
        parts.append(header + crlf + crlf)
        parts.append(str(value).encode("utf-8") + crlf)

    # File field
    mime_type, _ = mimetypes.guess_type(file_name)
    if not mime_type:
        mime_type = "application/octet-stream"

    file_header = ( f'Content-Disposition: form-data; name="{file_field}"; filename="{file_name}"' ).encode("utf-8")
    parts.append(b"--" + boundary_bytes + crlf)
    parts.append(file_header + crlf)
    parts.append(f"Content-Type: {mime_type}".encode("utf-8") + crlf + crlf)
    parts.append(file_bytes + crlf)

    # Closing boundary
    parts.append(b"--" + boundary_bytes + b"--" + crlf)

    body = b"".join(parts)
    content_type = f"multipart/form-data; boundary={boundary}"
    return body, content_type


def do_presigned_post(r1, tr, file_name, file_bytes):
    # Did we get a presigned post?
    obj = r1.json()
    if "error" in obj and obj["error"]:
        raise TestFail(f"api/post-image returned error: {obj['error']}")

    presigned_post = obj["presigned_post"]
    s3_url = presigned_post["url"]
    s3_fields = presigned_post["fields"]

    body, content_type = make_multipart_body(s3_fields,
                                             file_field="file",
                                             file_name=file_name,
                                             file_bytes=file_bytes)

    r2 = tr.http_get(s3_url,
                      method='POST',
                      data = body,
                      timeout = UPLOAD_TIMEOUT_SECONDS,
                      headers = { 'Content-Type':content_type,
                                  'Content-Length': str(len(body))
                                 })

    return r2

################################################################
### TESTS FOLLOW ###############################################
################################################################

### BASIC TESTS

@timeout(5)
def test_autograder_key_present( tr:TestRunner ):
    """
    The autograder key must exist in ubuntu's authorized_keys.
    """
    auth_path = "/home/ubuntu/.ssh/authorized_keys"
    try:
        txt = tr.read_file(auth_path)
    except Exception as e:  # pragma: no cover - surfaced to student clearly
        raise TestFail(f"Cannot read {auth_path}", context=str(e)) from e
    # Require the exact key line (comment is part of it)
    assert_contains(txt, AUTO_GRADER_KEY_LINE)

### VIRTUAL ENVIRONMENT

@timeout(5)
def test_venv_present( tr:TestRunner):
    """Require {labdir}/.venv"""
    labdir = tr.ctx.labdir
    r = tr.run_command(f"test -x {labdir}/.venv/bin/python")
    if r.exit_code != 0:
        raise TestFail(f"lab directory {labdir} does not contain virtual environment (expected .venv/bin/python)")

    r = tr.run_command(f"cd {labdir}; poetry run python -c 'print(0)'")
    if r.exit_code != 0:
        raise TestFail(f"'cd {labdir}; poetry run python' does not work {labdir}")

    return f"virtual environment configured in {labdir} and 'poetry run python' command works."

### SERVICE FILES
@timeout(5)
def test_service_file_installed( tr:TestRunner):
    fn = f"/etc/systemd/system/{tr.ctx.lab}.service"
    r = tr.run_command(f"test -x {fn}")
    if r.exit_code != 0:
        raise TestFail(f"{fn} does not exist. Did you install the {tr.ctx.lab}.service file?")
    raise f"{fn} exists."

@timeout(5)
def test_service_not_enabled( tr:TestRunner):
    fn = f"/etc/systemd/system/{tr.ctx.lab}.service"
    r = tr.run_command(f"test -x {fn}")
    if r.exit_code == 0:
        raise TestFail(f"WARNING: {tr.ctx.lab}.service is enabled! Please disable it so that the service does not automatically start if your instance is rebooted.")
    raise f"{tr.ctx.lab}.service is not enabled, so it will not start automatically if your instance is rebooted.")



@timeout(5)
def test_nginx_config_syntax_okay( tr:TestRunner):
    r = tr.run_command("sudo nginx -t")
    if r.exit_code != 0:
        raise TestFail("nginx -t failed", context=r.stderr)
    return "nginx configuration validates"

@timeout(5)
def test_gunicorn_running( tr:TestRunner ):
    lab = tr.ctx.lab
    r = tr.run_command("ps auxww")
    if r.exit_code != 0:
        raise TestFail("could not run ps auxww")
    count = 0
    for line in r.stdout.split("\n"):
        if (lab in line) and (".venv/bin/gunicorn") in line:
            count += 1
    if count==0:
        raise TestFail(f"Could not find {lab} gunicorn running")
    return f"Found {count} {'copy' if count==1 else 'copies'} of {lab} gunicorn process running (1 or more are required)"

def test_database_created( tr:TestRunner):
    fname = tr.ctx.labdir + "/instance/message_board.db"
    r = tr.run_command(f"stat {fname}")
    if r.exit_code !=0:
        raise TestFail(f"database file {fname} has not been created (e.g. Did you run `make init-db`?")

    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE api_keys" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE api_keys' statement. "
                       "Run make wipe-db and then make init-db.")

    tr.ctx.database_fname = fname
    return f"database {fname} created and schema validated"

@timeout(5)
def test_api_keys_exist( tr: TestRunner):
    lab = tr.ctx.lab
    lab_answers = None
    for filepath in (f"/home/ubuntu/{lab}-answers.yaml",f"/home/ubuntu/{lab}/{lab}-answers.yaml"):
        try:
            lab_answers = tr.read_file(filepath)
            break
        except Exception:  # noqa: BLE001 pylint: disable=broad-exception-caught
            continue
    if lab_answers is None:
        raise TestFail(f"Could not find {lab}-answers.yaml. Please create this file and grade again")
    try:
        data = yaml.safe_load(lab_answers)
    except yaml.scanner.ScannerError as e:
        raise TestFail(f"""
        ***********************************
        *** INVALID YAML FOUND IN {filepath}
        ***********************************

        Invalid content:

        {lab_answers}
        """) from e
    try:
        tr.ctx.api_key = data['API_KEY']  # Dynamic field, use dict access
    except KeyError as e:
        raise TestFail(f"API_KEY: not in {lab}-answers.yaml {e}") from e
    try:
        tr.ctx.api_secret_key = data['API_SECRET_KEY']  # Dynamic field, use dict access
    except KeyError as e:
        raise TestFail(f"API_SECRET_KEY: not in {lab}-answers.yaml {e}") from e
    return f"API_KEY <{tr.ctx.api_key}> and API_SECRET_KEY <censored> read from {lab}-answers.yaml"


def get_database_tables( tr:TestRunner ):
    tr.ctx.table_rows = {}  # clear the .table_rows
    fname = tr.ctx.database_fname
    r = tr.run_command(f"sqlite3 {fname} .schema")
    for (table,_) in [("api_keys","API Keys"),
                         ("messages","messages")]:
        r = tr.run_command(f"sqlite3 {fname} -json 'select * from {table}'")
        if r.exit_code != 0:
            raise TestFail(f"could not select * from {table} for {fname}")

        try:
            tr.ctx.table_rows[table] = r.json() if r.stdout else []
        except json.decoder.JSONDecodeError as e:
            raise TestFail(f"JSONDecodeError {e} could not decode: {r.stdout}") from e


@timeout(5)
def test_database_tables( tr:TestRunner):
    if tr.ctx.api_key is None:
        raise TestFail(f"Could not complete test because api_key cannot be read from {tr.ctx.lab}-answers.yaml")

    fname = tr.ctx.database_fname
    get_database_tables(tr)
    assert tr.ctx.table_rows is not None

    # Now make sure that the api_key in the config file is in the database
    count = 0
    for row in tr.ctx.table_rows['api_keys']:
        if row['api_key']==tr.ctx.api_key:
            count += 1
    if count==0:
        raise TestFail(f"api_key {tr.ctx.api_key} is in answers file but not table 'api_key' of database {fname}")
    return f"Successfully found API Keys from {CONFIG_FILE} in {fname}"


@retry(times=3, backoff=0.25)
@timeout(10)
def test_https_root_ok( tr:TestRunner):
    lab = tr.ctx.lab
    url = f"https://{tr.ctx.labdns}/"
    r = tr.http_get(url, tls_info=True)
    if r.status != 200:
        raise TestFail(f"Expected 200 at {url}, got {r.status}", context=r.headers)
    assert_contains(r.text, re.compile(lab, re.I), context=3)
    return f"Correct webserver running on {url}"


def post_image( tr:TestRunner, image_bytes, image_name):
    # post a message and verify it is there
    magic = int(time.time())
    msg = f'test post {image_name} image magic number {magic}'
    url = f"https://{tr.ctx.labdns}/api/post-image"

    image_size = len(image_bytes)
    r1 = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,
                                                  'api_secret_key' : tr.ctx.api_secret_key,
                                                  'message': msg,
                                                  'image_data_length': image_size
                                                 }).encode("utf-8"))
    if r1.status < 200 or r1.status >= 300:
        raise TestFail(f"POST to {url} error={r1.status} {r1.text}")

    # Now upload image to S3
    r2 = do_presigned_post(r1, tr, image_name, image_bytes)
    if r2.status < 200 or r2.status >= 300:
        raise TestFail(f"Error uploading image to S3: status={r2.status}, body={r2.text!r}")

    # Verify that the posted message is in the databsae
    get_database_tables(tr)
    assert tr.ctx.table_rows is not None

    count = 0
    for row in tr.ctx.table_rows['messages']:
        if row['message']==msg:
            logger.info('message_id %s match: %s',row['message_id'],row['message'])
            count += 1
        else:
            logger.debug('no match: %s',row['message'])

    if count==0:
        raise TestFail(f"posted {image_name} with magic number {magic} in the database but message not found.")

    # Verify that get-images returns Lincoln
    url2 = f"https://{tr.ctx.labdns}/api/get-images"
    r3 = tr.http_get(url2)
    if r3.status < 200 or r3.status >= 300:
        raise TestFail(f"could not http GET to {url2} error={r3.status} {r3.text}")
    download_url = None
    count = 0
    for row in r3.json():
        if row['message']==msg and row.get('url'):
            download_url = row['url']
            count += 1

    if count==0:
        raise TestFail(f"posted message magic number {magic} in database but not returned by {url2}")

    if download_url is None:
        raise TestFail(f"posted message magic number {magic} in database but no download url is returned by {url2}")


    # Finally, download the image
    r4 = tr.http_get(download_url)
    if r4.status < 200 or r3.status >= 300:
        raise TestFail(f"Could not download image from {download_url} rr={r4}")

    # Make sure that it's the right image
    if not r4.content:
        raise TestFail("Could not download content from S3")

    if len(r4.content) !=image_size:
        raise TestFail(f"Downloaded content is {len(r4.content)} bytes; expected {image_size}")

    if r4.content != image_bytes:
        raise TestFail("Downloaded content is the right size but wrong content???")

    return f"Image API request to {url} is successful, image uploaded to S3, validated to be in the database, and downloaded from S3"
