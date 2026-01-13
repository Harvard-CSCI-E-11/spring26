"""
lab3 tester
"""

# pylint: disable=duplicate-code
import json
import re
import urllib.parse
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, TestFail
from e11.lab_tests.lab_common import (
    test_service_file_installed,
    test_service_not_enabled,
    test_autograder_key_present,
    test_venv_present,
    test_nginx_config_syntax_okay,
    test_gunicorn_running,
)

# Imported test functions are used by test discovery system (see grader.collect_tests_in_definition_order)
imported_tests = [
    test_service_file_installed,
    test_service_not_enabled,
    test_autograder_key_present,
    test_venv_present,
    test_nginx_config_syntax_okay,
    test_gunicorn_running,
]

@retry(times=3, backoff=0.25)
@timeout(10)
def test_https_root_ok( tr:TestRunner):
    lab = tr.ctx.lab
    url = f"https://{tr.ctx.labdns}/"
    r = tr.http_get(url, tls_info=True)
    if r.status != 200:
        error_msg = f"Expected 200 at {url}, got {r.status}"
        if r.status == 0 and r.text:
            error_msg += f" - {r.text}"
        raise TestFail(error_msg, context=r.headers)
    if "Hello from Flask" in r.text:
        raise TestFail(f"{lab}.service appears to be serving server:app and not student_server:app. "
                       f"You need to edit /etc/systemd/system/{lab}.service as root to fix this. "
                       f"Then run systemctl daemon-reload followed by systemctl restart {lab}")
    assert_contains(r.text, re.compile(lab, re.I), context=3)
    return f"Correct webserver running on {url}"

@timeout(5)
def test_sqlite3_installed( tr:TestRunner):
    r = tr.run_command("sqlite3 :memory: 'select 1;'")
    if r.exit_code != 0:
        raise TestFail("sqlite3 command not found - install it with 'sudo apt install sqlite3'")
    return "sqlite3 installed"

@timeout(5)
def test_database_created( tr:TestRunner):
    fname = tr.ctx.labdir + "/students.db"
    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE students" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE students' statement")

    return "database created"

@timeout(5)
def test_database_loaded( tr:TestRunner):
    fname = tr.ctx.labdir + "/students.db"
    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE students" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE students' statement")

    r = tr.run_command(f"sqlite3 {fname} -json 'select * from students'")
    if r.exit_code != 0:
        raise TestFail(f"could not select * from students for {fname}")
    students = json.loads(r.stdout)
    s0 = students[0]
    tr.ctx['s0'] = s0  # Dynamic field, use dict access
    return f"Successfully found {len(students)} students in the database. First student is {s0}"


@timeout(5)
def test_database_search( tr:TestRunner):
    url = f"https://{tr.ctx.labdns}/"
    s0 = tr.ctx['s0']  # Dynamic field, use dict access
    student_id = s0.get('student_id','n/a')
    r = tr.http_get(url, method='POST', data=urllib.parse.urlencode({ 'student_id': student_id }).encode("utf-8"))
    if r.status != 200:
        error_msg = f"could not http POST to {url} for {student_id}"
        if r.status == 0 and r.text:
            error_msg += f" - {r.text}"
        raise TestFail(error_msg)
    assert_contains(r.text, student_id)
    return f"Search for {student_id} found the student"

@timeout(5)
def test_database_sql_injection_fixed( tr:TestRunner):
    url = f"https://{tr.ctx.labdns}/"
    inject = 'asdf" or "a"="a'
    r = tr.http_get(url, method='POST', data=urllib.parse.urlencode({ 'student_id': inject }).encode("utf-8"))
    if r.status != 200:
        error_msg = f"could not http POST to {url} for SQL Injection {inject}"
        if r.status == 0 and r.text:
            error_msg += f" - {r.text}"
        raise TestFail(error_msg)
    count = r.text.count("<tr>")
    if count>0:
        raise TestFail(f"SQL injection returned {count} records; it should have returned 0.")
    return "SQL Injection bug fixed"
