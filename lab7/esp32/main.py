# main.py will run on the ESP32 to upload an image.
# It can also be run from the Python command line on a laptop to test the upload

UPLOAD_INTERVAL_SECONDS = 10
UPLOAD_ATTEMPTS = 6

# GPIO 2 controls the flash LED
ESP32_WROVER_BLUE_LED_PIN = 2

ERROR_FIRST_POST_FAILED = 3
ERROR_S3_POST_FAILED = 4
ERROR_CAMERA_INIT_FAILED = 5

from config import API_KEY,API_SECRET_KEY,POST_IMAGE_URL

import sys
import time

data = {'frames_uploaded':0}

# Is my script running on Micropython?
try:
    # use led.off() to turn it on (it's active-low)
    # and led.on() to turn it off.
    from machine import Pin
    led = Pin(ESP32_WROVER_BLUE_LED_PIN, Pin.OUT)
    led.on()
except ImportError:
    led = None

# Import urequests on micropython, else import requests as urequests
if led is not None:
    import urequests
else:
    import requests as urequests

def error_led(message, times, delay=0.2):
    """Function for flashing the blue LED"""
    print(message)
    if led is None:
        return
    for _ in range(times):
        led.off()
        time.sleep(delay)
        led.on()
        time.sleep(delay)

def post_image(image):
    #
    # first use /api/post-image to get the presigned post
    #
    uploaded = data["frames_uploaded"]+1
    data["frames_uploaded"] = uploaded

    obj = {'api_key':API_KEY,
           'api_secret_key':API_SECRET_KEY,
           'message':f' frame {uploaded}'
           }

    r = urequests.post(POST_IMAGE_URL, data = obj)
    if not r.ok:
        print("url=",POST_IMAGE_URL,"r=",r,r.text)
        error_led("first post failed",ERROR_FIRST_POST_FAILED)
        raise RuntimeError("first post failed")
    presigned_post = r.json()['presigned_post']
    r.close()

    # now upload to S3 using the presigned post and a hand-crafted file POST
    # since Micropython doesn't have the files= option.
    boundary = "----MicroPythonFormBoundary"

    # Construct multipart form data
    body = b''
    for key, value in presigned_post['fields'].items():
        body += b'--' + boundary.encode() + b'\r\n'
        body += b'Content-Disposition: form-data; name="%s"\r\n\r\n' % key.encode()
        body += value.encode() + b'\r\n'

    # Add file field
    body += b'--' + boundary.encode() + b'\r\n'
    body += b'Content-Disposition: form-data; name="file"; filename="image.jpg"\r\n'
    body += b'Content-Type: image/jpeg\r\n\r\n'
    body += image + b'\r\n'
    body += b'--' + boundary.encode() + b'--\r\n'

    # Prepare headers
    headers = {
        'Content-Type': 'multipart/form-data; boundary=' + boundary,
        'Content-Length': str(len(body))
    }

    # POST the request
    r = urequests.post(presigned_post["url"], data=body, headers=headers)

    print("Status:", r.status_code)
    print("Response:", r.text)
    r.close()

    if not r.ok:
        error_led("S3 upload failed",ERROR_S3_POST_FAILED)
        raise RuntimeError("second post failed")
    print(f"[{time.time()}] Uploaded frame {uploaded}")
    return

#
# Actual program for running in MicroPython
#
if led is not None:
    import camera

    camera.deinit()
    if not camera.init(0, d0=4, d1=5, d2=18, d3=19, d4=36, d5=39, d6=34, d7=35,format=camera.JPEG, framesize=camera.FRAME_VGA, xclk_freq=camera.XCLK_20MHz, href=23, vsync=25, reset=-1, pwdn=-1,sioc=27, siod=26, xclk=21, pclk=22,fb_location=camera.PSRAM):
        error_led("Camera init failed", ERROR_CAMERA_INIT_FAILED)
        raise RuntimeError("Camera init failed")

    # Take 5 photos and upload them every 10 seconds
    for n in range(UPLOAD_ATTEMPTS):
        print("taking picture",n)
        image = camera.capture()
        post_image(image)
        time.sleep(UPLOAD_INTERVAL_SECONDS)


#
# Test program for running on MacOS
#
if (led is None) and (__name__=='__main__'):
    import argparse
    parser = argparse.ArgumentParser(description='Upload an image',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("image")
    args = parser.parse_args()
    try:
        with open(args.image,"rb") as f:
            image = f.read()
    except Exception as e:
        print(f"Failed to read image: {e}")
        sys.exit(1)

    post_image(image)
