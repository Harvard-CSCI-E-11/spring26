# SPDX-FileCopyrightText: 2025 Simson Garfinkel (Customized)
# License: Unlicense
# more exmaples can be found at https://github.com/adafruit/Adafruit_CircuitPython_PyCamera/blob/main/examples/
"""
camera3.py:

This program takes photos and uploads them to the dashboard and the student server.
It uses Wi-Fi and the Network Time Protocol to set the Real Time Clock

Learning guide for the MEMENTO:
https://github.com/adafruit/Adafruit_Learning_System_Guides/tree/main/MEMENTO

API Reference for the adafruit_pycamera library:
https://docs.circuitpython.org/projects/pycamera/en/stable/api.html

"""

import os
import ssl
import time
import sys
import io
import re

import adafruit_ntp
import adafruit_pycamera
import adafruit_requests
import rtc
import socketpool
import wifi
from displayio import Bitmap

# 1. SETUP WIFI AND NTP

SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
EMAIL   = os.getenv("EMAIL")
COURSE_KEY = os.getenv("COURSE_KEY")
LAB = os.getenv("LAB")

DASHBOARD_ENDPOINT = "https://csci-e-11.org/api/v1"


if not SSID or not PASSWORD:
    print("WiFi config not found in settings.toml.")
    sys.exit(0)

print(f"\n\nConnecting to {SSID}...")
try:
    wifi.radio.connect(SSID,PASSWORD)
except ConnectionError:
    print(f"Cannot connect to WiFi ssid: {SSID} password: {PASSWORD}")
    sys.exit(0)

if not wifi.radio.connected:
    print("Wifi failed to connect. Exiting.")
    sys.exit(0)


print(f"Connected to {os.getenv('CIRCUITPY_WIFI_SSID')}.")
print("My IP address is", wifi.radio.ipv4_address)
pool = socketpool.SocketPool(wifi.radio)
requests = adafruit_requests.Session(pool, ssl.create_default_context())
r = requests.get("http://ip-api.com/json/?fields=offset")
current_offset_seconds = r.json()['offset']
utc_offset = current_offset_seconds // 3600
ntp = adafruit_ntp.NTP(pool, server="pool.ntp.org", tz_offset=utc_offset)
print(f"NTP time: {ntp.datetime}")
rtc.RTC().datetime = ntp.datetime

def smash_email(email):
    """Convert an email into the CSCI E-11 smashed email.
    Remove underbars and plus signs"""
    email    = re.sub(r'[^-a-zA-Z0-9@.]', '', email).lower().strip()
    smashed_email = "".join(email.replace("@",".").split(".")[0:2])
    return smashed_email


# 2. CAMERA & LED SETUP
pycam = adafruit_pycamera.PyCamera()
pycam.resolution = 2  # 2 is 640x480;  12 is 2560x1920
pycam.camera.quality = 4  # decent compression

def presigned_post_to_s3(presigned_data, jpeg):
    url = presigned_data['url']
    fields = presigned_data['fields']
    print("presigned_data:",presigned_data)
    print("url:",url)
    print("fields:",fields)
    
    # now upload to S3 using the presigned post and a hand-drafted file POST
    boundary = '----FormBoundary'
    eboundary = boundary.encode()
    eol  = b'\r\n'
    body = bytearray()
    
    def add_part(name, value):
        body.extend(b"--" + eboundary + eol)
        body.extend(('Content-Disposition: form-data; name="%s"' % name).encode("utf-8"))
        body.extend(eol + eol)
        body.extend(str(value).encode("utf-8"))
        body.extend(eol)
  
    
    for k, v in fields.items():
        add_part(k, v)
    
    # Add the file itself
    body.extend(b'--' + eboundary + eol)
    body.extend(b'Content-Disposition: form-data; name="file"; filename="image.jpg"' + eol)
    body.extend(b'Content-type: image/jpeg' + eol*2)
    body.extend(bytes(jpeg))
    body.extend(eol)
    
    # *** required closing boundary ***
    body.extend(b"--" + eboundary + b"--" + eol)
    
    
    # prepare the headers
    headers = {
        'Content-Type': 'multipart/form-data; boundary=' + boundary,
        'Content-Length': str(len(body))
    }
    
    # build the multipart form

    r = requests.post(url, data=body, headers=headers, timeout=10)

    print("Status Code:", r.status_code)
    if r.status_code >= 400:
        print("Error:", r.text)
    

def post_to_dashboard(jpeg):
    """Send the jpeg to the CSCI E-11 dashboard"""
    pycam.tone(1000,0.1)
    auth = {"email":EMAIL, "course_key":COURSE_KEY}
    r = requests.post(DASHBOARD_ENDPOINT,
                      json={'action':'post-image', 'auth':auth},
                      timeout=10)
    if r.status_code//100 !=2:
        print("post-image failed. r=",r," text==",r.text)
        return

    result = r.json()
    presigned_post_to_s3(result['presigned_post'], jpeg)    
    pycam.tone(1100,0.1)
    return

def post_to_imageboard(jpeg):
    """send the jpeg to the student imageboard"""
    pycam.tone(2000,0.1)
    url = f"https://{smash_email(EMAIL)}-{LAB}.csci-e-11.org/api/post-image"
    form_data = { 'api_key': API_KEY,
                  'api_secret_key' : API_SECRET_KEY,
                  'message' : "sent from MEMENTO"}
    print("url",url)
    r = requests.post(url,
                      data=form_data,
                      timeout=10)
    if r.status_code//100 !=2:
        print("post to imageboard failed. r=",r," text==",r.text)
        return

    result = r.json()
    presigned_post_to_s3(result['presigned_post'], jpeg)
    pycam.tone(2100,0.1)
    return

pycam.tone(400, 0.1)   # Play a ready tone
pycam.tone(600, 0.05)

def valid_jpeg(jpeg):
    return (jpeg.startswith(b"\xFF\xD8")
            and ((jpeg.endswith(b"\xFF\xD9") or jpeg.rfind(b"\xFF\xD9") > len(b) - 8)))

while True:
    frame = pycam.continuous_capture()
    if isinstance(frame,Bitmap):
        pycam.blit(frame)
        
    pycam.keys_debounce()

    # SHUTTER: Focus and then photo
    if pycam.shutter.short_count:
        pycam.tone(220, 0.05)
        pycam.autofocus()
        pycam.tone(330, 0.05)
        pycam.tone(440, 0.1)
        # grab the jpeg memoryview and immediate turn it into a byte array
        jpeg = pycam.capture_into_jpeg()
        if jpeg is not None:
            jpeg = bytes(jpeg)
        # Go back into live preview
        pycam.live_preview_mode()
        if jpeg is None:
            print("jpeg is NONE.")
            pycam.tone(100,0.2)
            continue
        # Vadliate the jpeg
        if not valid_jpeg(jpeg):
            print("jpeg does not validate")
            pycam.tone(150,0.2)
            continue
        pycam.tone(660, 0.1)
        post_to_dashboard(jpeg)
        ### Uncomment this to post to your imageboard
        ### post_to_imageboard(jpeg)

    # EXIT: Clean unmount and final report
    if pycam.ok.fell:
        pycam.unmount_sd_card()
        pycam.tone(660,0.1)
        pycam.tone(440,0.1)
        pycam.tone(220,0.1)
        sys.exit()