"""
Python CLI Leaderboard Client
"""
import time
import sys
import json
import requests


# pylint: disable=invalid-name
TIMEOUT = 30
ENDPOINT = 'https://leaderboard.csci-e-11.org/'

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug',action='store_true')
    parser.add_argument('endpoint',default=ENDPOINT,nargs='?')
    args = parser.parse_args()

    url_register = f'{args.endpoint}api/register'
    url_update = f'{args.endpoint}api/update'

    response = requests.get(url_register,timeout = TIMEOUT)
    try:
        my_data = response.json()
    except json.decoder.JSONDecodeError:
        print(f"Invalid JSON from {url_register}: {response.text}")
        sys.exit(1)

    name = my_data['name']
    opaque = my_data['opaque']
    print(f"name={name} opaque={opaque} type={type(opaque)}" )

    while True:
        response = requests.post(url_update,
                                 data={'opaque': opaque},
                                 timeout = TIMEOUT )
        if args.debug:
            print(f"Posted: {response.status_code}  "
                  f"response={response.text}  {type(response.text)}")
        try:
            data = response.json()
        except json.decoder.JSONDecodeError:
            print(f"Invalid JSON from {url_update}: {response.text}")
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
