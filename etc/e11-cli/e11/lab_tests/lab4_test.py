"""
lab4 tester
"""
# pylint: disable=duplicate-code

import json
import random
import re
import urllib.parse

from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, TestFail

from . import lab_common

test_autograder_key_present = lab_common.test_autograder_key_present
test_venv_present = lab_common.test_venv_present
test_nginx_config_syntax_ok = lab_common.test_nginx_config_syntax_okay
test_gunicorn_running = lab_common.test_gunicorn_running
test_database_created = lab_common.test_database_created
test_api_keys_exist = lab_common.test_api_keys_exist
test_database_tables = lab_common.test_database_tables

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

@timeout(5)
def test_invalid_api_key( tr:TestRunner):
    # test posting with an invalid API key
    msg = 'this should not be posted'
    url = f"https://{tr.ctx.labdns}/api/post-message"
    r = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,
                                                  'api_secret_key' : 'invalid',
                                                  'message': msg
                                                 }).encode("utf-8"))
    if r.status == 200:
        raise TestFail(f"attempt to post to {url} with invalid API key was successful: error={r.status} {r.text}")
    return "Cannot post with invalid API key."

@timeout(5)
def test_post_message( tr:TestRunner):
    # post a message and verify it is there
    magic = random.randint(0,10000)
    msg = f'hello from the automatic grader magic number {magic}'
    url = f"https://{tr.ctx.labdns}/api/post-message"
    r = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,  # Dynamic field
                                                  'api_secret_key' : tr.ctx.api_secret_key,  # Dynamic field
                                                  'message': msg
                                                 }).encode("utf-8"))
    if r.status != 200:
        raise TestFail(f"could not http POST to {url} error={r.status} {r.text}")

    # Now see if the posted message is in the databsae
    lab_common.get_database_tables(tr)
    count = 0
    for row in tr.ctx.table_rows['messages']:
        if row['message']==msg:
            count += 1
    if count==0:
        raise TestFail("posted message did not get entered into the database")

    # Make sure the API works to get the posted message
    url2 = f"https://{tr.ctx.labdns}/api/get-messages"
    r = tr.http_get(url2)
    if r.status != 200:
        raise TestFail(f"could not http POST to {url2} error={r.status} {r.text}")
    rows = json.loads(r.text)
    for row in rows:
        if row['message']==msg:
            count += 1

    if count==0:
        raise TestFail(f"posted message in database but not returned by {url2}")

    return f"Post message to {url} is successful, and validated to be in the database, and returned by {url2}"
