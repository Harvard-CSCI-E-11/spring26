"""
lab4 tester
"""
# pylint: disable=duplicate-code

import os.path
import json
import re
import urllib.parse
import configparser
import random
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, TestFail
from e11.lab_tests import lab_common

def test_venv_present( tr:TestRunner):
    return lab_common.test_venv_present(tr)

def test_nginx_config_syntax_ok( tr:TestRunner):
    return lab_common.test_nginx_config_syntax_okay( tr )

def test_gunicorn_running( tr:TestRunner ):
    return lab_common.test_gunicorn_running(tr)


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

def test_database_created( tr:TestRunner):
    return lab_common.test_database_created( tr )

def test_database_keys( tr: TestRunner):
    return lab_common.test_database_keys(tr)

@timeout(5)
def test_post_message( tr:TestRunner):
    fname = tr.ctx['labdir'] + "/instance/message_board.db"
    magic = random.randint(0,10000)
    msg = f'hello from the automatic grader magic number {magic}'
    url = f"https://{tr.ctx['labdns']}/api/post-message"
    r = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx['api_key'],
                                                  'api_secret_key' : tr.ctx['api_secret_key'],
                                                  'message': msg
                                                 }).encode("utf-8"))
    if r.status != 200:
        raise TestFail(f"could http POST to {url} error={r.status} {r.text}")

    # Now see if it is in the databsae
    r = tr.run_command(f"sqlite3 {fname} -json 'select * from messages'")
    rows = json.loads(r.stdout)
    count = 0
    for row in rows:
        if row['message']==msg:
            count += 1
    if count==0:
        raise TestFail("posted message did not get entered into the database")

    # make sure the api works
    url2 = f"https://{tr.ctx['labdns']}/api/get-messages"
    r = tr.http_get(url2)
    if r.status != 200:
        raise TestFail(f"could http POST to {url2} error={r.status} {r.text}")
    rows = json.loads(r.text)
    for row in rows:
        if row['message']==msg:
            count += 1

    if count==0:
        raise TestFail(f"posted message in database but not returned by {url2}")

    return f"Post message to {url} is successful, and validated to be in the database, and returned by {url2}"
