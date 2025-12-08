"""
lab6 tester
"""
# pylint: disable=duplicate-code

import json
import time
import urllib.parse

from e11.e11core.utils import get_logger
from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
from e11.lab_tests.nicols import nicols_jpeg
from e11.lab_tests.harvard import harvard_jpeg
from e11.lab_tests.lab_common import (
    do_presigned_post,
    get_database_tables,
    post_image,
    test_autograder_key_present,
    test_venv_present,
    test_nginx_config_syntax_okay,
    test_gunicorn_running,
    test_database_created,
    test_api_keys_exist,
    test_database_tables,
    test_https_root_ok,
)

# Imported test functions are used by test discovery system (see grader.collect_tests_in_definition_order)
imported_tests = [
    test_autograder_key_present,
    test_venv_present,
    test_nginx_config_syntax_okay,
    test_gunicorn_running,
    test_database_created,
    test_api_keys_exist,
    test_database_tables,
    test_https_root_ok,
]

IMAGE_TOO_BIG = 5_000_000

logger = get_logger()

@timeout(5)
def test_post_image1( tr:TestRunner):
    return post_image( tr, nicols_jpeg(), "nicols.jpeg")

@timeout(5)
def test_post_image2( tr:TestRunner):
    return post_image( tr, harvard_jpeg(), "harvard.jpeg")

@timeout(5)
def verify_rekognition_enabled( tr:TestRunner ):
    r = tr.run_command("aws rekognition list-collections")
    if r.exit_code != 0:
        raise TestFail("AWS Rekognition API not authorized")

    if "CollectionIds" not in r.text:
        raise TestFail("AWS Rekognition API not authorized")
    return "AWS Rekognition API authorized for Instance"

@timeout(5)
def verify_rekognition_celeb( tr:TestRunner ):
    url = f"https://{tr.ctx.labdns}/api/get-images"
    r = tr.http_get(url)
    if r.status < 200 or r.status >= 300:
        raise TestFail(f"could not http GET to {url} error={r.status} {r.text}")
    for row in r.json():
        for celeb in row.get('celeb',[]):
            if celeb.get('Name','')=="Nichelle Nichols":
                return "Found Nichelle Nichols"
    raise TestFail("Could not find Nichelle Nichols")
