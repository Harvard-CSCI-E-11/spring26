"""
lab8 tester
"""
# pylint: disable=duplicate-code

from typing import Tuple

# This is very similar to the lab6 tester...

from boto3.dynamodb.conditions import Key

from e11.e11_common import get_user_from_email,queryscan_table,s3_client, users_table, A
from e11.e11core.utils import get_logger
from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
from e11.lab_tests.nicols import nicols_jpeg
from e11.lab_tests.harvard import harvard_jpeg
from e11.lab_tests.lab_common import (
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

NOT_JPEG_SOI = "not a JPEG (missing SOI 0xFFD8)"
JPEG_NO_EXIF = "JPEG verified; no EXIF in header ({why})"

################################################################
## ChatGPT code for validating jpeg without using an image library

# pylint: disable=too-many-return-statements
def _find_jpeg_app1_exif_segment(data: bytes) -> Tuple[bool, str]:
    """
    Scan JPEG segments. Return (has_exif, reason).
    Detects EXIF stored in APP1 (0xFFE1) with payload starting b'Exif\\x00\\x00'.
    """
    n = len(data)
    if n < 4:
        return False, "too short"

    i = 2  # after SOI
    while True:
        # Skip any fill bytes / stray 0xFFs
        while i < n and data[i] == 0xFF:
            i += 1
        if i >= n:
            return False, "reached end"

        marker = data[i]
        i += 1

        # Standalone markers (no length)
        if marker in (0xD8, 0xD9) or (0xD0 <= marker <= 0xD7) or marker == 0x01:
            if marker == 0xD9:  # EOI
                return False, "reached EOI"
            continue

        # Start of Scan: compressed image data follows until EOI; don't parse past this.
        if marker == 0xDA:
            return False, "reached SOS (no EXIF in header segments)"

        # All other markers should have a 2-byte big-endian length (includes the length bytes)
        if i + 1 >= n:
            return False, "truncated segment length"
        seglen = (data[i] << 8) | data[i + 1]
        i += 2
        if seglen < 2:
            return False, "invalid segment length"
        payload_len = seglen - 2
        if i + payload_len > n:
            return False, "truncated segment payload"

        if marker == 0xE1:  # APP1
            payload = data[i : i + payload_len]
            if payload.startswith(b"Exif\x00\x00"):
                return True, "found APP1 Exif"
        i += payload_len

def is_jpeg_no_exif(data: bytes) -> Tuple[bool, str]:
    """
    Returns (ok, message) where ok means:
      - data looks like a JPEG (SOI)
      - and no EXIF APP1 segment is present before SOS/EOI
    """
    assert isinstance(data, (bytes, bytearray, memoryview))

    b = bytes(data)

    # JPEG signature: SOI 0xFFD8
    if len(b) < 2 or b[0:2] != b"\xFF\xD8":
        return False, NOT_JPEG_SOI

    has_exif, why = _find_jpeg_app1_exif_segment(b)
    if has_exif:
        return False, f"JPEG has EXIF ({why})"
    return True, JPEG_NO_EXIF.format(why=why)


# Example:
# ok, msg = is_jpeg_no_exif(data)
# print(ok, msg)
# if not ok:
#     raise ValueError(msg)

################################################################


@timeout(5)
def test_post_image1( tr:TestRunner):
    return post_image( tr, nicols_jpeg(), "nicols.jpeg")

@timeout(5)
def test_post_image2( tr:TestRunner):
    return post_image( tr, harvard_jpeg(), "harvard.jpeg")

@timeout(5)
def test_rekognition_enabled( tr:TestRunner ):
    r = tr.run_command("aws rekognition list-collections")
    if r.exit_code != 0:
        raise TestFail("AWS Rekognition API not authorized")

    if "CollectionIds" not in r.text:
        raise TestFail("AWS Rekognition API not authorized")
    return "AWS Rekognition API authorized for Instance"

@timeout(5)
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

@timeout(5)
def test_rekognition_text( tr:TestRunner ):
    url = f"https://{tr.ctx.labdns}/api/get-images"
    r = tr.http_get(url)
    if r.status < 200 or r.status >= 300:
        raise TestFail(f"could not http GET to {url} error={r.status} {r.text}")
    for row in r.json():
        for dt in row.get('detected_text',[]):
            if "harvard" in dt.get("DetectedText","").lower():
                return "Found Harvard"
    raise TestFail("Could not find Harvard")

@timeout(5)
def test_memento_dashboard( tr:TestRunner ):
    user =  get_user_from_email(tr.ctx.email)
    kwargs:dict = {'KeyConditionExpression' : (
	Key(A.USER_ID).eq(user.user_id) &
        Key(A.SK).begins_with(A.SK_IMAGE_PREFIX)
    )}
    items = queryscan_table(users_table.query, kwargs)

    # Now try to get the images.
    # We don't need to use presigned posts because we are running with permissions
    success = 0
    msgs = []
    for item in items:
        data = s3_client.get_object(Bucket=item[A.BUCKET], Key=item[A.KEY])['Body'].read()
        ok, msg = is_jpeg_no_exif(data)
        msgs.append(msg)
        if ok:
            success += 1
    if success>0:
        return "\n".join(msgs)
    if success == 0:
        raise TestFail("No images uploaded to dashboard")
    raise TestFail("\n".join(msgs))
