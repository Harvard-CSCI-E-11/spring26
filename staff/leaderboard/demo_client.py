"""
Python CLI Demo Code (demo_client.py)
"""
import time
import json

import requests

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('endpoint')
    parser.add_argument('name')
    parser.add_argument('key')
    args = parser.parse_args()
    URL = f'{args.endpoint}/api/update'

    while True:
        response = requests.post(URL,
                                 data={'name': args.name,
                                       'key': args.key},
                                 timeout = 30 )
        print(f"Posted: {response.status_code}")

        leaderboard = requests.get(f'http://{args.endpoint}/api/leaderboard', timeout=30).json()
        print(json.dumps(leaderboard))
        time.sleep(60)
