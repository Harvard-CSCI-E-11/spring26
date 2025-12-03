"""
main.py will run on the ESP32 to upload an image.
It can also be run from the Python command line on a laptop to test the upload
"""
import os
import ssl

import wifi
import socketpool
import adafruit_requests
import adafruit_pycamera

# ---- WiFi setup ----
SSID = os.getenv("CIRCUITPY_WIFI_SSID","")
PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD","")
API_KEY = os.getenv("API_KEY","")
API_SECRET_KEY = os.getenv("API_SECRET_KEY","")
SMASHED_EMAIL = os.getenv("SMASHED_EMAIL","")

print("Connecting to", SSID)
wifi.radio.connect(SSID, PASSWORD)
print("Connected, IP:", wifi.radio.ipv4_address)

pool = socketpool.SocketPool(wifi.radio)
ssl_context = ssl.create_default_context()
requests = adafruit_requests.Session(pool, ssl_context)

# ---- Camera setup ----
pycam = adafruit_pycamera.PyCamera()
# Optionally tweak resolution/effect here, e.g.:
# pycam.resolution = "640x480"

def take_picture():
    """Take the picture"""
    print("Capturing JPEG...")
    jpeg_bytes = pycam.capture_into_jpeg()
    if jpeg_bytes is None:
        raise RuntimeError("Camera capture failed")
    print("JPEG size:", len(jpeg_bytes), "bytes")
    return jpeg_bytes

def post_picture(jpeg_bytes):
    """Post the picture"""
    # ---- Build a minimal multipart/form-data body ----
    boundary = "---------------------------cpmemento123456"
    body_start = (
        "--" + boundary + "\r\n"
        'Content-Disposition: form-data; name="file"; filename="photo.jpg"\r\n'
        "Content-Type: image/jpeg\r\n"
        "\r\n"
    )
    body_end = "\r\n--" + boundary + "--\r\n"

    body = body_start.encode("utf-8") + jpeg_bytes + body_end.encode("utf-8")

    headers = {
        "Content-Type": "multipart/form-data; boundary=" + boundary
    }

    url = "https://"+SMASHED_EMAIL+"-lab6.csci-e-11.org/api/post-image"


    print("POST", url)
    resp = requests.post(url, data=body, headers=headers)

    print("Status:", resp.status_code)
    print("Response:", resp.text[0:100])

pic = take_picture()
post_picture(pic)
