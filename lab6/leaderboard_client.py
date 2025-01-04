"""
ESP32 Leaderboard Client
"""

import os
import time
import wifi
import adafruit_connection_manager
import adafruit_requests

# WiFi configuration - Update This!
ssid = os.getenv("CIRCUITPY_WIFI_SSID")
password =os.getenv("CIRCUITPY_WIFI_PASSWORD")


TIMEOUT = 30
ENDPOINT = "https://leaderboard.csci-e-11.org/"
HIDDEN = "hidden value"

# Connect to WiFi
print("Connecting to WiFi...")
wifi.radio.connect(ssid, password)
print("Connected to WiFi")
print("IP Address:", wifi.radio.ipv4_address)

# Get requests operational

pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
requests = adafruit_requests.Session(pool, ssl_context)

if True:
    url_register = ENDPOINT + "api/register"
    url_update = ENDPOINT + "api/update"
    response = requests.get(url_register, timeout=TIMEOUT)
    my_data = response.json()
    name = my_data["name"]
    opaque = my_data["opaque"]
    print("Name: ", name)

run = 0
while True:
    run += 1
    print("\nrun:",run)
    response = requests.post(url_update, data={"opaque": opaque}, timeout=TIMEOUT)
    data = response.json()
    now = int(time.time())
    count = 0
    for leader in data["leaderboard"]:
        if leader.get("active", False) == True:
            if leader["name"] == name:
                me = "me -->"
            else:
                me = ""
            age = now - int(leader["first_seen"])
            if (count < 4) or me:
                print(count, me, leader["name"], age)
        count += 1
    time.sleep(10)
