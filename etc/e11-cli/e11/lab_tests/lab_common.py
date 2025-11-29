"""
lab_common.py: common things for the lab tester.
"""
import re
import json
import yaml

from e11.e11core.decorators import retry, timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail,assert_contains

CONFIG_FILE = "/home/ubuntu/e11-config.ini"
AUTO_GRADER_KEY_LINE = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIEK/6zvwwWOO+ui4zbUYN558g+LKh5N8f3KpoyKKrmoR "
    "auto-grader-do-not-delete"
)


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


@timeout(5)
def test_venv_present( tr:TestRunner):
    """Require {labdir}/.venv"""
    labdir = tr.ctx.labdir
    r = tr.run_command(f"test -x {labdir}/.venv/bin/python")
    if r.exit_code != 0:
        raise TestFail(f"lab directory {labdir} does not contain virtual environment (expected .venv/bin/python)")
    return f"virtual environment configured in {labdir}"

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
        if f"{lab}/.venv/bin/gunicorn" in line:
            count += 1
    if count==0:
        raise TestFail(f"Could not find {lab} gunicorn running")
    return f"Found {count} {'copy' if count==1 else 'copies'} of {lab} gunicorn running"

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
    data = yaml.safe_load(lab_answers)
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
            tr.ctx.table_rows[table] = json.loads(r.stdout) if r.stdout else []
        except json.decoder.JSONDecodeError as e:
            raise TestFail(f"JSONDecodeError {e} could not decode: {r.stdout}") from e


@timeout(5)
def test_database_tables( tr:TestRunner):
    fname = tr.ctx.database_fname
    get_database_tables(tr)

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
