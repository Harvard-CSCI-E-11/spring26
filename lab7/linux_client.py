"""
Python CLI Leaderboard Client.
This is for students who are not able to purchase a MEMENTO
"""
import time
import sys
import json
import requests


# pylint: disable=invalid-name
EMAIL    = ""                   # enter your email here
COURSE_KEY = ""                 # enter your course key here
TIMEOUT = 30
ENDPOINT = "https://leaderboard.csci-e-11.org/"

URL_REGISTER = ENDPOINT + "api/register"
URL_UPDATE = ENDPOINT + "api/update"

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug',action='store_true')
    parser.add_argument('endpoint',default=ENDPOINT,nargs='?')
    args = parser.parse_args()

    response = requests.get(URL_REGISTER,
                            data = {"email":EMAIL,
                                    "course_key":COURSE_KEY},
                            timeout = TIMEOUT)
    try:
        my_data = response.json()
    except json.decoder.JSONDecodeError:
        print(f"Invalid JSON from {URL_REGISTER}: {response.text}")
        sys.exit(1)

    name = my_data['name']
    opaque = my_data['opaque']
    print(f"name={name} opaque={opaque} type={type(opaque)}" )

    while True:
        response = requests.post(URL_UPDATE,
                                 data={'opaque': opaque},
                                 timeout = TIMEOUT )
        if args.debug:
            print(f"Posted: {response.status_code}  "
                  f"response={response.text}  {type(response.text)}")
        try:
            data = response.json()
        except json.decoder.JSONDecodeError:
            print(f"Invalid JSON from {URL_UPDATE}: {response.text}")
            sys.exit(1)
        print("Message: ",data['message'])
        print("Leaderboard:")
        now = int(time.time())
        for active in (True,False):
            if active:
                print("Active Leaders:")
            else:
                print("Inactive:")
            for leader in data['leaderboard']:
                if leader.get('active',False) == active:
                    me  = 'me -->' if leader['name']==name else ''
                    age = now - int(leader['first_seen'])
                    print(me, leader['name'],age)
            print("")
        time.sleep(10)
