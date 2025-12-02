"""
lab5 tester
"""
# pylint: disable=duplicate-code

import json
import random
import urllib.parse
from pathlib import Path

from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
from e11.lab_tests.lab_common import (
    make_multipart_body,
    get_database_tables,
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

LINCOLN_JPEG = Path(__file__).parent / "lincoln.jpeg"
UPLOAD_TIMEOUT_SECONDS = 10


@timeout(5)
def test_post_image( tr:TestRunner):
    # post a message and verify it is there
    magic = random.randint(0,1000000)
    msg = f'hello from the automatic grader magic number {magic}'
    url = f"https://{tr.ctx.labdns}/api/post-image"

    image = LINCOLN_JPEG
    image_size = image.stat().st_size
    r1 = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,
                                                  'api_secret_key' : tr.ctx.api_secret_key,
                                                  'message': msg,
                                                  'image_data_length': image_size
                                                 }).encode("utf-8"))
    if r1.status < 200 or r1.status >= 300:
        raise TestFail(f"POST to {url} error={r1.status} {r1.text}")

    # Did we get a presigned post?
    obj = r1.json()
    if "error" in obj and obj["error"]:
        raise RuntimeError(f"api/post-image returned error: {obj['error']}")

    presigned_post = obj["presigned_post"]
    s3_url = presigned_post["url"]
    s3_fields = presigned_post["fields"]

    body, content_type = make_multipart_body(s3_fields, file_field="file", file_path=image)

    r2 = tr.http_get(s3_url,
                      method='POST',
                      data = body,
                      timeout = UPLOAD_TIMEOUT_SECONDS,
                      headers = {
                          'Content-Type':content_type,
                          'Content-Length': str(len(body)),
                      })


    if r2.status < 200 or r2.status >= 300:
        raise RuntimeError(f"Error uploading image to S3: status={r2.status}, body={r2.text!r}")

    # Now see if the posted message is in the databsae
    get_database_tables(tr)
    assert tr.ctx.table_rows is not None

    count = 0
    for row in tr.ctx.table_rows['messages']:
        if row['message']==msg:
            count += 1
    if count==0:
        raise TestFail("posted message did not get entered into the database")

    # Make sure the API works to get the posted message
    url2 = f"https://{tr.ctx.labdns}/api/get-messages"
    r3 = tr.http_get(url2)
    if r3.status < 200 or r3.status >= 300:
        raise TestFail(f"could not http POST to {url2} error={r3.status} {r3.text}")
    rows = json.loads(r3.text)
    download_url = None
    for row in rows:
        if row['message']==msg:
            download_url = row['url']
            count += 1

    if count==0:
        raise TestFail(f"posted message in database but not returned by {url2}")

    if download_url is None:
        raise TestFail(f"posted message in database but no download url is returned by {url2}")

    # Finally, download the
    r4 = tr.http_get(download_url)
    if r4.status < 200 or r3.status >= 300:
        raise TestFail(f"Could not download image from {download_url} rr={r4}")

    # Make sure that it's the right size
    if not r4.content:
        raise TestFail("Could not download content from S3")

    if len(r4.content) !=image_size:
        raise TestFail(f"Downloaded content is {len(r4.content)} bytes; expected {image_size}")

    return f"Image API request to {url} is successful, image uploaded to S3, validated to be in the database, and downloaded from S3"

@timeout(5)
def test_too_big_image( tr:TestRunner):
    # post a message and verify it is there
    msg = 'Trying to post too large an image...'
    url = f"https://{tr.ctx.labdns}/api/post-message"
    r = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,
                                                  'api_secret_key' : tr.ctx.api_secret_key,
                                                  'message': msg
                                                 }).encode("utf-8"))
    if r.status != 200:
        raise TestFail(f"could not http POST to {url} error={r.status} {r.text}")
