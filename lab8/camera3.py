# SPDX-FileCopyrightText: 2025 Simson Garfinkel (Customized)
# License: Unlicense
# more exmaples can be found at https://github.com/adafruit/Adafruit_CircuitPython_PyCamera/blob/main/examples/
"""
This program takes photos and uploads them to the server.
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

import adafruit_ntp
import adafruit_pycamera
import adafruit_requests
import rtc
import socketpool
import wifi

# 1. SETUP WIFI AND NTP

SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
EMAIL   = os.getenv("EMAIL")
COURSE_KEY = os.getenv("COURSE_KEY")


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

# 2. CAMERA & LED SETUP
pycam = adafruit_pycamera.PyCamera()
pycam.resolution = 2  # 2 is 640x480;  12 is 2560x1920
pycam.camera.quality = 4  # decent compression

def post_to_dashboard(jpeg):
    """Send the jpeg to the CSCI E-11 dashboard"""
    return

def post_to_imageboard(jpeg):
    """send the jpeg to the student imageboard"""
    return

pycam.tone(400, 0.1)   # Play a ready tone
pycam.tone(600, 0.05)
pycam.live_preview_mode()


while True:
    pycam.blit(pycam.continuous_capture())
    pycam.display.refresh()
    pycam.keys_debounce()

    # SHUTTER: Focus and then photo
    if pycam.shutter.short_count:
        pycam.tone(220, 0.05)
        pycam.autofocus()
        pycam.tone(330, 0.05)
        pycam.tone(440, 0.1)
        jpeg = pycam.capture_into_jpeg()
        pycam.tone(660, 0.1)
        print("jpeg=",jpeg)

        post_to_dashboard(jpeg)
        post_to_imageboard(jpeg)

    # EXIT: Clean unmount and final report
    if pycam.ok.fell:
        pycam.unmount_sd_card()
        pycam.display.root_group = displayio.Group()
        pycam.display_message(f"EXIT\nTotal: {photo_count}", color=0x00FF00)
        pycam.tone(660,0.1)
        pycam.tone(440,0.1)
        pycam.tone(220,0.1)
        sys.exit()
