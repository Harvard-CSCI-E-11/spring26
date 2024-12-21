import time
import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_requests import Session
from adafruit_ssd1351 import SSD1351
import wifi
import socketpool
import ssl
import adafruit_requests

# WiFi configuration
WIFI_SSID = "WIFI2"
WIFI_PASSWORD = "PASSWORD1"

# HTTPS POST configuration
URL = "https://test.com/"
POST_DATA = {
    "foo": "key",
    "bar": "value"
}

# TFT Display setup
displayio.release_displays()
spi = board.SPI()
cs = board.D9
dc = board.D10
reset = board.D11

# Initialize display
display_bus = displayio.FourWire(spi, command=dc, chip_select=cs, reset=reset)
WIDTH = 128
HEIGHT = 128
BORDER = 2

display = SSD1351(display_bus, width=WIDTH, height=HEIGHT)

# Connect to WiFi
def connect_to_wifi():
    print("Connecting to WiFi...")
    wifi.radio.connect(WIFI_SSID, WIFI_PASSWORD)
    print("Connected to WiFi")
    print("IP Address:", wifi.radio.ipv4_address)

# Display text on the TFT screen
def display_text(message):
    splash = displayio.Group()
    color_bitmap = displayio.Bitmap(WIDTH, HEIGHT, 1)
    color_palette = displayio.Palette(1)
    color_palette[0] = 0x000000  # Black background

    bg_sprite = displayio.TileGrid(color_bitmap, pixel_shader=color_palette, x=0, y=0)
    splash.append(bg_sprite)

    text_area = label.Label(terminalio.FONT, text=message, color=0xFFFFFF, x=10, y=HEIGHT // 2)
    splash.append(text_area)

    display.show(splash)

# HTTPS POST request
def send_post_request():
    pool = socketpool.SocketPool(wifi.radio)
    session = adafruit_requests.Session(pool, ssl.create_default_context())

    print("Sending POST request to", URL)
    response = session.post(URL, json=POST_DATA)
    print("Response code:", response.status_code)
    print("Response text:", response.text)

    display_text(response.text[:50])  # Display first 50 characters of the response

# Main execution
try:
    connect_to_wifi()
    send_post_request()
except Exception as e:
    display_text("Error:\n" + str(e))
    print("Error:", e)

while True:
    time.sleep(1)
