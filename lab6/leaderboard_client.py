"""
ESP32 Leaderboard Client
"""

import time
import wifi
import adafruit_connection_manager
import adafruit_requests
import random

# WiFi configuration - Update This!
secrets = {
    "ssid": getenv("CIRCUITPY_WIFI_SSID"),
    "password": getenv("CIRCUITPY_WIFI_PASSWORD"),
}

TIMEOUT = 30
ENDPOINT = "https://leaderboard.csci-e-11.org/"
HIDDEN = "hidden value"

# Connect to WiFi
def connect_to_wifi():
    print("Connecting to WiFi...")
    wifi.radio.connect(secrets["ssid"], secrets["password"])
    print("Connected to WiFi")
    print("IP Address:", wifi.radio.ipv4_address)


# Main execution
try:
    connect_to_wifi()
except Exception as e:
    print("Error Connecting to Wifi:", e)

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

while True:
    response = requests.post(url_update, data={"opaque": opaque}, timeout=TIMEOUT)
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
