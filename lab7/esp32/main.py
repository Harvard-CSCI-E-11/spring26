# main.py will run on the ESP32 to upload an image.
# It can also be run from the Python command line on a laptop to test the upload

UPLOAD_INTERVAL_SECONDS = 2
UPLOAD_TIMEOUT_SECONDS = 60

from config import API_KEY,API_SECRET_KEY,POST_IMAGE_URL

import sys
import requests
import time

data = {'frames_uploaded':0}

# Is my script running on Micropython?
try:
    from machine import Pin
    led = Pin(4, Pin.OUT)  # GPIO 4 controls the flash LED
except ImportError:
    led = None


def error_led(message, times, delay=0.2):
    print(message)
    if led is None:
        return
    for _ in range(times):
        led.on()
        time.sleep(delay)
        led.off()
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

    r = requests.post(POST_IMAGE_URL, data = obj)
    if not r.ok:
        print("url=",POST_IMAGE_URL,"r=",r,r.text)
        error_led("first post failed",3)
        raise RuntimeError("first post failed")

    # now upload to S3 using the presigned post
    presigned_post = r.json()['presigned_post']
    r = requests.post(presigned_post['url'], data=presigned_post['fields'], files={'file':image})
    if not r.ok:
        error_led("S3 upload failed",4)
        raise RuntimeError("second post failed")
    print("Uploaded frame",uploaded)
    return

if (led is None) and (__name__=='__main__'):
    import argparse
    parser = argparse.ArgumentParser(description='Upload an image',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("image")
    args = parser.parse_args()
    with open(args.image,"rb") as f:
        image = f.read()
        post_image(image)
