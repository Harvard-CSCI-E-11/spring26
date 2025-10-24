"""
lab4 tester
"""
# pylint: disable=duplicate-code

import os.path
import json
import re
import urllib.parse
import configparser
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, TestFail

CONFIG_FILE = "/home/ubuntu/e11-config.ini"

@timeout(5)
def test_venv_present( tr:TestRunner):
    # Require lab3 .venv
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
    lab = tr.ctx['lab']
    r = tr.run_command("ps auxww")
    if r.exit_code != 0:
        raise TestFail("could not run ps auxww")
    count = 0
    for line in r.stdout.split("\n"):
        if f"{lab}/.venv/bin/gunicorn" in line:
            count += 1
    if count==0:
        raise TestFail(f"Could not find {lab} gunicorn running")
    return f"Found {count} {'copy' if count==1 else 'copies'} of lab3 gunicorn running"

@retry(times=3, backoff=0.25)
@timeout(10)
def test_https_root_ok( tr:TestRunner):
    lab = tr.ctx['lab']
    url = f"https://{tr.ctx['labdns']}/"
    r = tr.http_get(url, tls_info=True)
    if r.status != 200:
        raise TestFail(f"Expected 200 at {url}, got {r.status}", context=r.headers)
    assert_contains(r.text, re.compile(lab, re.I), context=3)
    return f"Correct webserver running on {url}"

@timeout(5)
def test_database_created( tr:TestRunner):
    fname = tr.ctx['labdir'] + "/instance/message_board.db"
    if not os.path.exists(fname):
        raise TestFail(f"database file {fname} has not been created. Did you run `make init-db`?")

    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE api_keys" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE api_keys' statement. Run make wipe-db and then make init-db.")

    return f"database {fname} created and schema validated"

def get_lab4_config( tr:TestRunner ):
    txt = tr.read_file(CONFIG_FILE)
    cp = configparser.ConfigParser()
    try:
        cp.read_string( txt )
    except configparser.MissingSectionHeaderError as e:
        raise TestFail(f"{CONFIG_FILE} is not a valid configuration file") from e
    try:
        lab4 = cp['lab4']
    except KeyError as e:
        raise TestFail(f"{CONFIG_FILE} does not have a [lab4] section") from e
    try:
        api_key = lab4['api_key']
        api_secret_key = lab4['api_secret_key']
    except KeyError as e:
        raise TestFail(f"{CONFIG_FILE} [lab4] section requires both an api_key and an api_secret_key") from e
    return (api_key, api_secret_key)

@timeout(5)
def test_database_keys( tr:TestRunner):
    (api_key, api_secret_key) = get_lab4_config( tr )

    fname = tr.ctx['labdir'] + "/instance/message_board.db"
    r = tr.run_command(f"sqlite3 {fname} .schema")
    for (table,name) in [("api_keys","API Keys"),
                         ("messages","messages")]:
        r = tr.run_command(f"sqlite3 {fname} -json 'select * from {table}'")
        if r.exit_code != 0:
            raise TestFail(f"could not select * from {table} for {fname}")
        rows = json.loads(r.stdout)
        if len(rows)==0:
            raise TestFail(f"No {name} created")

        # Now make sure that the api_key in the config file is in the database
        if table=='api_keys':
            count = 0
            for row in rows:
                if row['api_key']==api_key:
                    count += 1
            if count==0:
                raise TestFail(f"api_key {api_key} is in {CONFIG_FILE} but not in {fname}")

    # remember the api_key and api_secret_key in the context
    tr.ctx['api_key'] = api_key
    tr.ctx['api_secret_key'] = api_secret_key
    return f"Successfully found API Keys in database and in {CONFIG_FILE}"


@timeout(5)
def test_post_message( tr:TestRunner):
    url = f"https://{tr.ctx['labdns']}/api/post-message"
    r = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx['api_key'],
                                                  'api_secret_key' : tr.ctx['api_secret_key'],
                                                  'message': 'hello from the automatic grader'
                                                 }).encode("utf-8"))
    if r.status != 200:
        raise TestFail(f"could http POST to {url} error={r.status} {r.text}")
    return f"Post message to {url} is successful"
