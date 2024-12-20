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
    parser.add_argument('hidden')
    args = parser.parse_args()
    url_update = f'{args.endpoint}/api/update'
    url_leaderboard = f'{args.endpoint}/api/leaderboard'

    while True:
        response = requests.post(url_update,
                                 data={'name': args.name,
                                       'hidden': args.hidden},
                                 timeout = 30 )
        print(f"Posted: {response.status_code}")

        leaderboard = requests.get(url_leaderboard, timeout=30).json()
        print(json.dumps(leaderboard))
        time.sleep(60)
