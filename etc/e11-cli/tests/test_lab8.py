"""
Validate the jpeg test in lab8.
lincoln.jpeg was created on the mac with Preview. It has an Exif.
livingroom.jpeg was created with a MOMENTO. It does not have an Exif.
"""

from e11.lab_tests.lab8_test import is_jpeg_no_exif
from e11.lab_tests.lincoln import lincoln_jpeg
from e11.lab_tests.livingroom import livingroom_jpeg

def test_jpeg():
    ok, why = is_jpeg_no_exif(livingroom_jpeg())
    print("livingroom: ",ok,why)
    assert ok==True

    ok, why = is_jpeg_no_exif(lincoln_jpeg())
    print("lincoln: ",ok,why)
    assert ok==False
