"""
Python 3.13 code that posts an image to the dashboard.
Taken from e11/main.py.
"""


import sys
from pathlib import Path

import requests

TIMEOUT = 10

if __name__=='__main__':
    import argparse
    parser = argparse.ArgumentParser(description="Test program for leaderboard",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('--debug',action='store_true')
    parser.add_argument('email',help='Enter your CSCI-E-11 email')
    parser.add_argument('course_key',help='Your course_key')
    parser.add_argument("imagefile",type=Path)
    args = parser.parse_args()

    if not args.imagefile.exists():
        print(f"{args.imagefile} does not exist")
        sys.exit(1)
    if not str(args.imagefile).endswith(".jpeg"):
        print(f"{args.imagefile} does end with .jpeg")
        sys.exit(1)
    print(f"uploading {args.imagefile}...")
    auth = {"email":args.email,
            "course_key":args.course_key}

    print(auth)
    r = requests.post("https://csci-e-11.org/api/v1",
                      json={'action':'post-image', 'auth':auth},
                      timeout = TIMEOUT )
    result = r.json()
    print(result)
    if result.get('error'):
        print("Cannot continue.")
        sys.exit(1)
    presigned_data= result['presigned_post']
    url = presigned_data['url']
    fields = presigned_data['fields']
    files = []

    # Construct the multipart form data
    # The 'file' MUST be the last element in the dictionary/list
    for key, value in fields.items():
        files.append((key, (None, value)))

    # Add the actual file data
    files.append(('file', (str(args.imagefile), args.imagefile.read_bytes())))

    # Perform the POST to S3
    # Note: No 'headers=headers' here; requests handles the Content-Type for multipart
    r = requests.post(url, files=files, timeout=TIMEOUT)

    print("Posted to S3. Result: ", r.status_code)
    if r.status_code >= 400:
        print("Error:", r.text)
