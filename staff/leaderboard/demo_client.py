"""
Python CLI Demo Code (demo_client.py)
"""
import time
import requests


# pylint: disable=invalid-name
TIMEOUT = 30
ENDPOINT = 'https://leaderboard.csci-e-11.org/'
URL_REGISTER = f'{ENDPOINT}/api/register'
URL_UPDATE = f'{ENDPOINT}/api/update'

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('name')
    parser.add_argument('hidden')
    args = parser.parse_args()

    my_data = requests.get(URL_REGISTER,timeout = TIMEOUT).json()
    name = my_data['name']
    opaque = my_data.json()['opaque']

    while True:
        response = requests.post(URL_UPDATE,
                                 data={'opaque': opaque},
                                 timeout = TIMEOUT )
        print(f"Posted: {response.status_code}")
        data = response.json()
        print("Message: ",data['message'])
        print("Leaderboard:")
        now = time.time()
        for leader in data['leaders']:
            me  = 'me -->' if leader['name']==name else ''
            age = now - leader['first_seen']
            active = 'active' if leader['active'] else ''
            print(me, leader['name'],age,active)
        time.sleep(60)
