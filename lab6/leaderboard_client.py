import time
import wifi
import adafruit_connection_manager
import adafruit_requests
import random

# Name you will post under. Update this!
NAME = 'update me'

# WiFi configuration - Update This!
WIFI_SSID = "CALA 203"
WIFI_PASSWORD = "grufgrufgruf"

# HTTPS POST configuration
URL = "https://leaderboard.csci-e-11.org/api/update"

# Your hidden key. If we use random.random(), it will change each time we run.
HIDDEN = 'hidden value'

# Connect to WiFi
def connect_to_wifi():
    print("Connecting to WiFi...")
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    print("Connected to WiFi")
    print("IP Address:", wifi.radio.ipv4_address)

# Main execution
try:
    connect_to_wifi()
except Exception as e:
    print("Error Connecting to Wifi:", e)

# Generate our hidden value

POST_DATA = {
    "name": NAME,
    "hidden": HIDDEN
}


count = 0

pool = adafruit_connection_manager.get_radio_socketpool(wifi.radio)
ssl_context = adafruit_connection_manager.get_radio_ssl_context(wifi.radio)
requests = adafruit_requests.Session(pool, ssl_context)

while True:
    requests.post(URL, data=POST_DATA)
    count += 1
    r = requests.get('https://leaderboard.csci-e-11.org/api/leaderboard')
    print('r=',r.text)
    time.sleep(5)
