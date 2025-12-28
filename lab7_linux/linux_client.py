"""
Python CLI Leaderboard Client.
This is for students who are not able to purchase a MEMENTO
"""
import time
import sys
import json
import requests
import tabulate


# pylint: disable=invalid-name
EMAIL    = ""                   # enter your email here
COURSE_KEY = ""                 # enter your course key here
TIMEOUT = 30
ENDPOINT = "https://leaderboard.csci-e-11.org/"
MAX_SLEEP = 5                   # maximum number of seconds to sleep

URL_REGISTER = ENDPOINT + "api/register"
URL_UPDATE = ENDPOINT + "api/update"

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug',action='store_true')
    parser.add_argument('--email',default=EMAIL)
    parser.add_argument('--course_key',default=COURSE_KEY)
    parser.add_argument('--seconds',type=int,default=10,
                        help='how many seconds to run the leaderboard')
    parser.add_argument("--method",default='GET',help='method to use')
    parser.add_argument("--user_agent")
    parser.add_argument('endpoint',default=ENDPOINT,nargs='?')
    args = parser.parse_args()
    headers = {}
    if args.user_agent:
        headers['User-Agent'] = args.user_agent

    response = requests.request(args.method,
                                URL_REGISTER,
                                data = {"email":args.email,
                                        "course_key":args.course_key},
                                headers = headers,
                                timeout = TIMEOUT)
    try:
        my_data = response.json()
    except json.decoder.JSONDecodeError:
        print(f"Invalid JSON from {URL_REGISTER}: {response.text}")
        sys.exit(1)

    name = my_data['name']
    opaque = my_data['opaque']
    print(f"name={name} opaque={opaque} type={type(opaque)}" )

    t0 = time.time()
    while True:
        response = requests.post(URL_UPDATE,
                                 data={'opaque': opaque},
                                 headers = headers,
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
            table = []
            if active:
                print("Active Leaders:")
            else:
                print("Inactive:")
            for leader in data['leaderboard']:
                if leader.get('active',False) == active:
                    me  = 'me -->' if leader['name']==name else ''
                    age = now - int(leader['first_seen'])
                    table.append([me,
                                  leader['name'],
                                  f"{age//60}:{age%60:02}",
                                  leader['ip_address'],
                                  leader['user_agent']])
            print(tabulate.tabulate(table))
            print("")
        time_till_timeout = (t0 + args.seconds) - time.time()
        print("time_till_timeout=",time_till_timeout)
        if time_till_timeout <= 0:
            break
        time.sleep( min(MAX_SLEEP, time_till_timeout) )
    print("Timeout expired.")
