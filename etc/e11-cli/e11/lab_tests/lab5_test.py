"""
lab5 tester
"""
# pylint: disable=duplicate-code

import json
import time
import urllib.parse
from pathlib import Path

from e11.e11core.utils import get_logger
from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
from e11.lab_tests.lab_common import (
    do_presigned_post,
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
IMAGE_TOO_BIG = 5_000_000

logger = get_logger()

@timeout(5)
def test_post_image( tr:TestRunner):
    # post a message and verify it is there
    magic = int(time.time())
    msg = f'test post Lincoln image magic number {magic}'
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

    # Now upload Lincoln to S3
    r2 = do_presigned_post(r1, tr, image.name, image.read_bytes())
    if r2.status < 200 or r2.status >= 300:
        raise TestFail(f"Error uploading image to S3: status={r2.status}, body={r2.text!r}")

    # Verify that the posted message is in the databsae
    get_database_tables(tr)
    assert tr.ctx.table_rows is not None

    count = 0
    for row in tr.ctx.table_rows['messages']:
        if row['message']==msg:
            logger.info('message_id %s match: %s',row['message_id'],row['message'])
            count += 1
        else:
            logger.debug('no match: %s',row['message'])

    if count==0:
        raise TestFail("posted image with magic number {magic} in the database but message not found.")

    # Verify that get-images returns Lincoln
    url2 = f"https://{tr.ctx.labdns}/api/get-images"
    r3 = tr.http_get(url2)
    if r3.status < 200 or r3.status >= 300:
        raise TestFail(f"could not http GET to {url2} error={r3.status} {r3.text}")
    rows = json.loads(r3.text)
    download_url = None
    count = 0
    for row in rows:
        if row['message']==msg and row.get('url'):
            download_url = row['url']
            count += 1

    if count==0:
        raise TestFail(f"posted message magic number {magic} in database but not returned by {url2}")

    if download_url is None:
        raise TestFail(f"posted message magic number {magic} in database but no download url is returned by {url2}")

    # Finally, test the download URL
    r4 = tr.http_get(download_url)
    if r4.status < 200 or r3.status >= 300:
        raise TestFail(f"Could not download image from {download_url} rr={r4}")

    # Make sure that it's the right image
    if not r4.content:
        raise TestFail("Could not download content from S3")

    if len(r4.content) !=image_size:
        raise TestFail(f"Downloaded content is {len(r4.content)} bytes; expected {image_size}")

    if r4.content != image.read_bytes():
        raise TestFail(f"Downloaded content is the right size but wrong content???")

    return f"Image API request to {url} is successful, image uploaded to S3, validated to be in the database, and downloaded from S3"

@timeout(5)
def test_too_big_image1( tr:TestRunner):
    """Ask to post an image that is too big."""
    magic = int(time.time())
    msg = f'Request to post image that is {IMAGE_TOO_BIG} bytes. Magic number {magic}'
    url = f"https://{tr.ctx.labdns}/api/post-image"

    args = { 'api_key': tr.ctx.api_key,
             'api_secret_key' : tr.ctx.api_secret_key,
             'message': msg,
             'image_data_length': IMAGE_TOO_BIG
            }
    r1 = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode(args).encode("utf-8"))

    if 200 <= r1.status < 300:
        raise TestFail(f"{url} does not reject posting an image of {IMAGE_TOO_BIG} bytes")

    return f"Image API correctly rejects attempt to upload image of {IMAGE_TOO_BIG} bytes"

@timeout(5)
def test_too_big_image2( tr:TestRunner):
    """Ask to post an image that is small but send one through that is too big."""
    magic = int(time.time())
    msg = f'Requesting to post 65536 bytes but actually posting {IMAGE_TOO_BIG} bytes. Magic number {magic}'
    url = f"https://{tr.ctx.labdns}/api/post-image"

    r1 = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,
                                                  'api_secret_key' : tr.ctx.api_secret_key,
                                                  'message': msg,
                                                  'image_data_length': 65536
                                                 }).encode("utf-8"))
    if r1.status < 200 or r1.status >= 300:
        raise TestFail(f"POST to {url} rejects posting of image that is 65536 bytes: error={r1.status} {r1.text}")

    # But now, post actually something that is 10 mbytes
    buf = b"X" * IMAGE_TOO_BIG
    r2 = do_presigned_post(r1, tr, "image.jpeg", buf)
    if 200 <= r2.status < 300:
        raise TestFail("Presigned post for S3 allowed uploading 10,000,000 bytes. Whoops.")

    return "S3 correctly blocked an attempt to upload 10,000,000 bytes."

@timeout(5)
def test_not_a_jpeg( tr:TestRunner):
    """Ask to post an image that is small but then send through bogus data."""
    magic = int(time.time())
    msg = f'Attempt to post an image that is not a JPEG. Magic number {magic}'
    url = f"https://{tr.ctx.labdns}/api/post-image"

    r1 = tr.http_get(url,
                    method='POST',
                    data=urllib.parse.urlencode({ 'api_key': tr.ctx.api_key,
                                                  'api_secret_key' : tr.ctx.api_secret_key,
                                                  'message': msg,
                                                  'image_data_length': 65536
                                                 }).encode("utf-8"))
    if r1.status < 200 or r1.status >= 300:
        raise TestFail(f"POST to {url} rejects posting of image that is 65536 bytes: error={r1.status} {r1.text}")

    # Now send bogus data
    buf = b"X" * 65536
    r2 = do_presigned_post(r1, tr, "image.jpeg", buf)
    if r2.status < 200 or r2.status > 300:
        raise TestFail("Presigned post did not upload to S3.")

    # Let's get the list of files and make sure that it's there there!
    # Give this 4 tries, each 0.5 seconds apart (sometimes it takes a whiel to delete)
    url2 = f"https://{tr.ctx.labdns}/api/get-images"
    r3 = tr.http_get(url2)
    if r3.status < 200 or r3.status >= 300:
        raise TestFail(f"could not http GET to {url2} error={r3.status} {r3.text}")
    rows = json.loads(r3.text)
    count = 0
    for row in rows:
        if row['message']==msg:
            logger.debug("Should not be present: %s",row)
            count += 1

    if count!=0:
        raise TestFail(f"posted message magic number {magic} with bogus JPEG is still in in database and returned by {url2}")
    return "Bogus JPEG that was uploaded is no longer in database"
