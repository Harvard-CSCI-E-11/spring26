"""
lab6 tester
"""
# pylint: disable=duplicate-code

from e11.e11core.utils import get_logger
from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
from e11.lab_tests.lab_common import (
    DEFAULT_TEST_TIMEOUT,
    test_service_file_installed,
    test_service_active,
    test_previous_lab_service_stopped,
    test_autograder_key_present,
    test_venv_present,
    test_nginx_config_syntax_okay,
    test_gunicorn_running,
    test_database_created,
    test_api_keys_exist,
    test_database_tables,
    test_https_root_ok,
    test_post_image1,
    test_post_image2
)

# Imported test functions are used by test discovery system (see grader.collect_tests_in_definition_order)
imported_tests = [
    test_venv_present,
    test_service_file_installed,
    test_service_active,
    test_previous_lab_service_stopped,
    test_autograder_key_present,
    test_nginx_config_syntax_okay,
    test_gunicorn_running,
    test_database_created,
    test_api_keys_exist,
    test_database_tables,
    test_https_root_ok,
    test_post_image1,
    test_post_image2
]

IMAGE_TOO_BIG = 5_000_000

logger = get_logger()

@timeout(DEFAULT_TEST_TIMEOUT)
def test_rekognition_enabled( tr:TestRunner ):
    r = tr.run_command("aws rekognition list-collections")
    if r.exit_code != 0:
        raise TestFail("AWS Rekognition API not authorized")

    if "CollectionIds" not in r.text:
        raise TestFail("AWS Rekognition API not authorized")
    return "AWS Rekognition API authorized for Instance"

@timeout(DEFAULT_TEST_TIMEOUT)
def test_rekognition_celeb( tr:TestRunner ):
    url = f"https://{tr.ctx.labdns}/api/get-images"
    r = tr.http_get(url)
    if r.status < 200 or r.status >= 300:
        raise TestFail(f"could not http GET to {url} error={r.status} {r.text}")
    for row in r.json():
        for celeb in row.get('celeb',[]):
            if celeb.get('Name','')=="Nichelle Nichols":
                return "Found Nichelle Nichols"
    raise TestFail("Could not find Nichelle Nichols")

@timeout(DEFAULT_TEST_TIMEOUT)
def test_rekognition_text( tr:TestRunner ):
    url = f"https://{tr.ctx.labdns}/api/get-images"
    r = tr.http_get(url)
    if r.status < 200 or r.status >= 300:
        raise TestFail(f"could not http GET to {url} error={r.status} {r.text}")
    try:
        for row in r.json():
            for dt in row.get('detected_text',[]):
                if "harvard" in dt.get("DetectedText","").lower():
                    return "Found Harvard"
    except Exception as e:      # pylint: disable=broad-exception-caught
        raise TestFail("could not decode API response. text='%s' error='%s",r.text, str(e)) from e
    raise TestFail("Could not find Harvard")
