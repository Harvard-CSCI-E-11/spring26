"""
MEMENTO Leaderboard Client
"""

import os
import time
import wifi                     # pyright: ignore[reportMissingModuleSource]
import adafruit_connection_manager
import adafruit_requests
import digitalio
import board
import sys
import displayio

# WiFi configuration
ssid     = os.getenv("CIRCUITPY_WIFI_SSID")
password = os.getenv("CIRCUITPY_WIFI_PASSWORD")

# --- Button Setup (The "Kill Switch") ---
# The Momento Shutter button is usually board.BUTTON
button = digitalio.DigitalInOut(board.BUTTON)
button.direction = digitalio.Direction.INPUT
button.pull = digitalio.Pull.UP

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

URL_REGISTER = ENDPOINT + "api/register"
URL_UPDATE = ENDPOINT + "api/update"

def register():
    """Register the Momento with the leaderboard"""
    response = requests.get(URL_REGISTER, timeout=TIMEOUT)
    my_data = response.json()
    name = my_data["name"]
    opaque = my_data["opaque"]
    print("Registered Name: ", name)
    return (name,opaque)

def run_leaderboard():
    """Run the leaderboard indefinately."""
    (name,opaque) = register()
    run = 0
    count = 0
    while True:
        run += 1
        print("\nrun:",run)
        response = requests.post(URL_UPDATE, data={"opaque": opaque}, timeout=TIMEOUT)
	data = response.json()
        now = int(time.time())
        for leader in data["leaderboard"]:
            if leader.get("active", False):
		if leader["name"] == name:
                    me = "me -->"
                else:
                    me = ""
                age = int(leader["last_seen"]) - int(leader["first_seen"])
                if (count < 4) or me:
                    print(count, me, leader["name"], age)
            count += 1
        # Wait for 10 seconds, checking the button every tenth of a second
        print("")
        for countdown in range(11,0,-1):
            print(f"Press V to exit. {countdown}... \r",end="")
            for _ in range(10):
                if not button.value:  # Button is pressed (Low)
                    print("Exit button pressed!")
                    return
                time.sleep(0.1)
        print("\n"*20)  # clear the screen

run_leaderboard()
