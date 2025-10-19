import json
import re
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, assert_not_contains, assert_len_between, TestFail
from e11.e11core.context import build_ctx

@timeout(5)
def test_venv_present( tr:TestRunner):
    # Require .venv exists (python_entry enforces; we also check explicitly)
    labdir = tr.ctx['labdir']
    r = tr.run_command(f"test -x {labdir}/.venv/bin/python")
    if r.exit_code != 0:
        raise TestFail("lab directory {labdir} does not contain virtual environment (expected .venv/bin/python)")
    return f"virtual environment configured in {labdir}"

@timeout(5)
def test_nginx_config_syntax_ok( tr:TestRunner):
    r = tr.run_command("sudo nginx -t")
    if r.exit_code != 0:
        raise TestFail("nginx -t failed", context=r.stderr)
    return "nginx configuration validates"

@timeout(5)
def test_gunicorn_running( tr:TestRunner ):
    r = tr.run_command("ps auxww")
    if r.exit_code != 0:
        raise TestFail("could not run ps auxww")
    count = 0
    for line in r.stdout.split("\n"):
        if "lab3/.venv/bin/gunicorn" in line:
            count += 1
    if count==0:
        raise TestFail("Could not find lab3 gunicorn running")
    return f"Found {count} {'copy' if count==1 else 'copies'} of lab3 gunicorn running"

@retry(times=3, backoff=0.25)
@timeout(10)
def test_https_root_ok( tr:TestRunner):
    url = f"https://{tr.ctx['labdns']}/"
    r = tr.http_get(url, tls_info=True)
    if r.status != 200:
        raise TestFail(f"Expected 200 at {url}, got {r.status}", context=r.headers)
    assert_contains(r.text, re.compile(r"lab3", re.I), context=3)

@timeout(5)
def test_database_created( tr:TestRunner):
    fname = tr.ctx['labdir'] + "/students.db"
    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE students" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE students' statement")

@timeout(5)
def test_database_loaded( tr:TestRunner):
    fname = tr.ctx['labdir'] + "/students.db"
    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE students" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE students' statement")

    r = tr.run_command(f"sqlite3 {fname} -json 'select * from students'")
    if r.exit_code != 0:
        raise TestFail(f"could not select * from studnets for {fname}")
    students = json.loads(r.stdout)
    s0 = students[0]
    return f"Successfully found {len(students)} students in the database. First student is {s0}"
