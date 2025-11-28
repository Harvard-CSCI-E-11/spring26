"""
lab_commnon.py: common things for the lab tester.
"""
import json
import os.path
import configparser

from e11.e11core.decorators import timeout
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
    # Require {labdir}/.venv
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
    return f"Found {count} {'copy' if count==1 else 'copies'} of lab3 gunicorn running"

@timeout(5)
def test_database_created( tr:TestRunner):
    fname = tr.ctx.labdir + "/instance/message_board.db"
    if not os.path.exists(fname):
        raise TestFail(f"database file {fname} has not been created. Did you run `make init-db`?")

    r = tr.run_command(f"sqlite3 {fname} .schema")
    if r.exit_code != 0:
        raise TestFail(f"could not get schema for {fname}")

    if "CREATE TABLE api_keys" not in r.stdout:
        raise TestFail(f"{fname} schema does not have a 'CREATE TABLE api_keys' statement. "
                       "Run make wipe-db and then make init-db.")

    return f"database {fname} created and schema validated"


def get_lab_config( tr:TestRunner ):
    """Gets the [lab4] or [lab5] config and puts the api_key and api_secret_key into the context"""
    lab = tr.ctx.lab
    txt = tr.read_file(CONFIG_FILE)
    cp = configparser.ConfigParser()
    try:
        cp.read_string( txt )
    except configparser.MissingSectionHeaderError as e:
        raise TestFail(f"{CONFIG_FILE} is not a valid configuration file") from e
    try:
        lab_cp = cp[ lab ]
    except KeyError as e:
        raise TestFail(f"{CONFIG_FILE} does not have a [{lab}] section") from e
    try:
        api_key = lab_cp['api_key']
        api_secret_key = lab_cp['api_secret_key']
    except KeyError as e:
        raise TestFail(f"{CONFIG_FILE} [{lab}] section requires both an api_key and an api_secret_key") from e
    tr.ctx['api_key'] = api_key  # Dynamic field, use dict access
    tr.ctx['api_secret_key'] = api_secret_key  # Dynamic field, use dict access
    return (api_key, api_secret_key)



@timeout(5)
def test_database_keys( tr:TestRunner):
    (api_key, _) = get_lab_config( tr )

    fname = tr.ctx.labdir + "/instance/message_board.db"
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

    return f"Successfully found API Keys in database and in {CONFIG_FILE}"
