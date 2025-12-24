"""
MEMENTO camera for Lab8

Camera docs: https://docs.circuitpython.org/projects/pycamera/en/stable/index.html

"""


import os
import ssl
import time
import rtc
import wifi
import socketpool
import adafruit_ntp
import adafruit_requests
import displayio
import terminalio
from adafruit_display_text import label
import keypad
import zipfile
import adafruit_pycamera
import board
import neopixel

# ---- Software Configuration from settings.toml ----
SSID = os.getenv("CIRCUITPY_WIFI_SSID")
PASSWORD = os.getenv("CIRCUITPY_WIFI_PASSWORD")
IMAGE_POST_API = os.getenv("LAB5_API")
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")
E11_EMAIL = os.getenv("E11_EMAIL")
E11_COURSE_KEY = os.getenv("E11_COURSE_KEY")


# ---- Hardware configuration ----
# This works for Simson's MEMENTO...
BUTTON_PINS = (
    board.BUTTON_UP,
    board.BUTTON_DOWN,
    board.BUTTON_LEFT,
    board.BUTTON_RIGHT,
    board.BUTTON_OK,
    board.BUTTON_SELECT,
)
KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_OK, KEY_SELECT = range(6)

RING_PIN = board.NEOPIXEL_RING     # adjust if different
RING_PIXELS = 8                    # 8 RGBW pixels
RING_BRIGHTNESS = 0.2

SECONDS_CHOICES = [1, 5, 10, 30, 60, 120, 180, 300, 600]

# ---- WiFi + NTP Setup ----
pool = None
requests = None
if SSID and PASSWORD:
    try:
        wifi.radio.connect(SSID, PASSWORD)
        pool = socketpool.SocketPool(wifi.radio)
        requests = adafruit_requests.Session(pool, ssl.create_default_context())
        ntp = adafruit_ntp.NTP(pool, server="pool.ntp.org")
        rtc.RTC().datetime = ntp.datetime
    except Exception as e:  # noqa: BLE001
        print("WiFi/NTP error:", e)
else:
    print("WiFi not configured; skipping NTP and HTTP.")

# ---- Camera + SD ----
pycam = adafruit_pycamera.PyCamera()
pycam.mode = 0          # JPEG
pycam.resolution = 2    # 640x480
pycam.effect = 0
pycam.led_level = 0
pycam.led_color = 3     # red, but we'll drive the ring directly

sd_mounted = False
try:
    pycam.mount_sd_card()
    sd_mounted = True
    print("SD mounted")
except Exception as e:  # noqa: BLE001
    print("No SD at startup:", e)

# ---- Display setup ----
# We require display.refresh()
display = pycam.display
display.auto_refresh = False

root = displayio.Group()
display.root_group = root

preview_bitmap = displayio.Bitmap(pycam.camera.width, pycam.camera.height, 65535)
preview_tilegrid = displayio.TileGrid(
    preview_bitmap,
    pixel_shader=displayio.ColorConverter(),
    x=0,
    y=(display.height - pycam.camera.height) // 2,
)
root.append(preview_tilegrid)
counter_label = label.Label(
    terminalio.FONT,
    text="",
    color=0xFFFFFF,
    scale=1,
    anchor_point=(0.5, 1.0),
    anchored_position=(display.width // 2, display.height - 1),
)
root.append(counter_label)

# ---- LED ring ----
ring = neopixel.NeoPixel(RING_PIN, RING_PIXELS, brightness=RING_BRIGHTNESS, auto_write=True)

# ---- Keys ----
keys = keypad.Keys(BUTTON_PINS, value_when_pressed=False, pull=True)

def update_ring(remaining, total):
    """ Flash the ring """
    if total <= 0:
        ring.fill((0, 0, 0, 0))
        return
    frac_done = (total - remaining) / total
    for i in range(RING_PIXELS):
        seg_start = i / RING_PIXELS
        seg_end = (i + 1) / RING_PIXELS
        if frac_done >= seg_end:
            level = 0.0
        elif frac_done <= seg_start:
            level = 1.0
        else:
            level = 1.0 - (frac_done - seg_start) / (seg_end - seg_start)
        level = max(0.0, min(1.0, level))
        ring[i] = (int(255 * level), 0, 0, 0)


# ---- Photo accounting ----
photo_count = 0
total_photo_bytes = 0

def sd_free_bytes():
    if not sd_mounted:
        return None
    try:
        st = os.statvfs("/sd")
        f_frsize = st[1]
        f_bavail = st[4]
        return f_frsize * f_bavail
    except (OSError,RuntimeError,ValueError) as e:
        print("statvfs error:", e)
        return None

def photos_possible():
    if not sd_mounted:
        return 0
    free_b = sd_free_bytes()
    if free_b is None:
        return 0
    avg = total_photo_bytes // photo_count if photo_count else 200_000
    if avg <= 0:
        return 0
    return int(free_b // (avg * 2))

def update_counter_label():
    counter_label.text = f"{photo_count}/{photos_possible()}"

update_counter_label()

# ---- Capture + upload ----
def capture_and_store():
    global photo_count, total_photo_bytes
    if not sd_mounted:
        return
    try:
        jpeg = pycam.capture_into_jpeg()
        if jpeg is None:
            return
        size = len(jpeg)
        photo_count += 1
        total_photo_bytes += size
        f = pycam.open_next_image("jpg")
        filename = f.name
        with f:
            f.write(jpeg)
        try:
            with zipfile.ZipFile("/sd/photos.zip", "a") as z:
                arcname = filename.split("/")[-1]
                z.write(filename, arcname=arcname)
        except Exception as e:  # noqa: BLE001
            print("zip write error:", e)
        try:
            os.remove(filename)
        except Exception:
            pass
        update_counter_label()
        if requests and IMAGE_POST_API and API_KEY and API_SECRET_KEY:
            try:
                resp = requests.post(
                    IMAGE_POST_API,
                    headers={
                        "X-API-KEY": API_KEY,
                        "X-API-SECRET-KEY": API_SECRET_KEY,
                    },
                    data=jpeg,
                    timeout=10,
                )
                resp.close()
            except Exception as e:  # noqa: BLE001
                print("HTTP error:", e)
    except RuntimeError as e:
        print("Capture error:", e)

# ---- Countdown state ----

def camera_snap():
    """Called when the shutter button is clicked. Take a photo and return."""

def main():
    """Main loop. Put the camera in streaming mode. Take a picture when the shutter button is pressed."""
    pycam.camera.continuous_capture_start()
    display.auth_refresh = False
    while True:
        pycam.camera.continuous_capture_get_frame()  # Grab the next frame
        display.refresh()                            # show it
        if display_on:
            frame = pycam.continuous_capture()
            preview_tilegrid.bitmap = frame

        now = time.monotonic()
        now_sec = int(now)

        if running and now_sec != last_second:
            delta = now_sec - last_second
            if delta > 0:
                remaining_seconds -= delta
                if remaining_seconds <= 0:
                    remaining_seconds = 0
                    running = False
                    countdown_label.text = "0"
                    update_ring(0, total_seconds)
                    pycam.tone(2000, 0.08)
                    if display_on:
                        flash_screen()
                    capture_and_store()
                    reset_countdown()
                else:
                    countdown_label.text = str(remaining_seconds)
                    update_ring(remaining_seconds, total_seconds)
            last_second = now_sec

        event = keys.events.get()
        while event:
            if event.pressed:
                if event.key_number == KEY_OK:
                    if remaining_seconds == 0:
                        reset_countdown()
                    running = not running
                    last_second = int(time.monotonic())
                elif event.key_number == KEY_SELECT:
                    reset_countdown()
                elif event.key_number == KEY_UP:
                    running = False
                    if duration_index < len(SECONDS_CHOICES) - 1:
                        duration_index += 1
                    total_seconds = SECONDS_CHOICES[duration_index]
                    reset_countdown()
                elif event.key_number == KEY_DOWN:
                    running = False
                    if duration_index > 0:
                        duration_index -= 1
                    total_seconds = SECONDS_CHOICES[duration_index]
                    reset_countdown()
                elif event.key_number in (KEY_LEFT, KEY_RIGHT):
                    display_on = not display_on
                    display.brightness = 1.0 if display_on else 0.0
            event = keys.events.get()

        # SD card hot-plug behavior
        pycam.keys_debounce()
        if pycam.card_detect.fell:
            print("SD removed")
            try:
                pycam.unmount_sd_card()
            except Exception:
                pass
            sd_mounted = False
            photo_count = 0
            total_photo_bytes = 0
            update_counter_label()
        if pycam.card_detect.rose:
            print("SD inserted")
            pycam.display_message("Mounting\nSD Card", color=0xFFFFFF)
            for _ in range(3):
                try:
                    pycam.mount_sd_card()
                    sd_mounted = True
                    break
                except OSError as exc:
                    print("Retry mount:", exc)
                    time.sleep(0.5)
            update_counter_label()

        countdown_label.text = str(remaining_seconds)
        time.sleep(0.1)

if __name__=="__main__":
    main()
