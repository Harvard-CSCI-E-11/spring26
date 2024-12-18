# Python CLI Demo Code (demo_client.py)
import time
import requests
import sys

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('endpoint')
    parser.add_argument('name')
    parser.add_argument('key')
    args = parser.parse_args()

    while True:
        response = requests.post(f'http://{parser.endpoint}/api/post',
                                 data={'name': parser.name,
                                       'key': parser.key})
        print(f"Posted: {response.status_code}")

        leaderboard = requests.get(f'http://{parser.endpoint}/api/leaderboard').json()
        print(json.dumps(leaderboard))
        time.sleep(60)
