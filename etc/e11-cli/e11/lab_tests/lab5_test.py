"""
lab5 tester
"""
# pylint: disable=duplicate-code

import re
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, TestFail
from e11.lab_tests import lab_common

test_autograder_key_present = lab_common.test_autograder_key_present
test_venv_present = lab_common.test_venv_present
test_nginx_config_syntax_ok = lab_common.test_nginx_config_syntax_okay
test_gunicorn_running = lab_common.test_gunicorn_running
test_database_created = lab_common.test_database_created
test_database_keys = lab_common.test_database_keys


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
def test_post_image( tr:TestRunner):
    # Use the API to get the signed S3 bucket info
    # Upload an image to S3
    # Get the image
    return f"Not yet implemented {tr}"
