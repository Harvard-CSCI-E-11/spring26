# SPDX-FileCopyrightText: 2025 Simson Garfinkel (Customized)
# License: Unlicense
# more examples can be found at
# https://github.com/adafruit/Adafruit_CircuitPython_PyCamera/blob/main/examples/
"""
This program takes photos. It uses Wi-Fi and the Network Time Protocol to set the Real Time Clock,
which is used to set the time on the images written to disk.

Learning guide for the MEMENTO:
https://github.com/adafruit/Adafruit_Learning_System_Guides/tree/main/MEMENTO

API Reference for the adafruit_pycamera library:
https://docs.circuitpython.org/projects/pycamera/en/stable/api.html

"""

import os
import ssl
import time
import sys

import adafruit_ntp
import adafruit_pycamera
import adafruit_requests
import rtc
import socketpool
import wifi
import displayio

# 1. SETUP WIFI AND NTP

SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")

if SSID and PASSWORD:
    print(f"\n\nConnecting to {SSID}...")
    try:
        wifi.radio.connect(SSID,PASSWORD)
    except ConnectionError:
        print(f"Cannot connect to WiFi ssid: {SSID}. Check password.")
else:
    print("WiFi config not found in settings.toml.")

if wifi.radio.connected:
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
else:
    print("Wifi failed to connect. Time not set.")


# 2. CAMERA & LED SETUP
pycam = adafruit_pycamera.PyCamera()

pycam.resolution = 2  # 2 is 640x480;  12 is 2560x1920
pycam.camera.quality = 4  # decent compression

# 3. STATS TRACKING
photo_count = 0
free_bytes = 0
total_bytes = 0

def update_sd_stats():
    """Sets free_bytes, total_bytes global variables"""
    global free_bytes, total_bytes # pylint: disable=global-statement
    fs_stat = os.statvfs("/sd")
    free_bytes = fs_stat[0] * fs_stat[3]
    total_bytes = fs_stat[0] * fs_stat[2]

# Make the pixels medium bright but turn them all off
def clear_leds():
    """Turns off the LEDs to off"""
    pycam.led_level = 2  # can be 0..4
    for i in range (8):
        pycam.pixels[i] = (0,0,0)
    pycam.pixels.show()

SPIN_TIME = 0.2
def spin_green_dot():
    """Spins a red dot around the ring in ~0.2 seconds"""
    pycam.pixels.auto_write = True  # update instantly
    for i in range(8):
        pycam.pixels[i] = (255,0,0)              # Next one red
        pycam.pixels[ (i-1)% 8] = (0,0,0)        # prev one off
        time.sleep( SPIN_TIME / 8)
    pycam.pixels[7] = (0,0,0)                    # turn off last one

def take_photo():
    "Focus and take a photo"
    print("")
    before = free_bytes
    pycam.capture_jpeg()        # apparently writes it to the sd!
    pycam.live_preview_mode()
    update_sd_stats()
    per_photo = before - free_bytes
    print("bytes used:",per_photo)
    if per_photo > 0:
        print("photos remaining:",free_bytes / per_photo)

update_sd_stats()
clear_leds()
pycam.tone(800, 0.1)   # Play a ready tone
pycam.tone(1200, 0.05)
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
        spin_green_dot()
        pycam.tone(440, 0.1)
        take_photo()
        pycam.tone(660, 0.1)

    # EXIT: Clean unmount and final report
    if pycam.ok.fell:
        pycam.unmount_sd_card()
        pycam.display.root_group = displayio.Group()
        pycam.display_message(f"EXIT\nTotal: {photo_count}", color=0x00FF00)
        pycam.tone(660,0.1)
        pycam.tone(440,0.1)
        pycam.tone(220,0.1)
        sys.exit()
