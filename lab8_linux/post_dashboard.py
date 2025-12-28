"""
Python 3.13 code that posts an image to the dashboard.
Taken from e11/main.py.
"""


import requests
import sys
from pathlib import Path
import requests

TIMEOUT = 10
if __name__=="__main__":
    print("Posting a photo to your dashboard")
    email = input("Enter your CSCI-E-11 email: ")
    course_key = input("Enter your Course Key: ")
    imagefile = Path(input("Name of file to upload: "))

    if not imagefile.exists():
        print(f"{imagefile} does not exist")
        sys.exit(1)
    if not str(imagefile).endswith(".jpeg"):
        print(f"{args.upload} does end with .jpeg")
        sys.exit(1)
    print(f"uploading {imagefile}...")
    auth = {"email":email,
            "course_key":course_key}

    r = requests.post("https://csci-e-11.org/api/v1",
                      json={'action':'post-image', 'auth':auth},
                      timeout = TIMEOUT )
    result = r.json()
    print(result)
    presigned_data= result['presigned_post']
    url = presigned_data['url']
    fields = presigned_data['fields']
    files = []

    # Construct the multipart form data
    # The 'file' MUST be the last element in the dictionary/list
    for key, value in fields.items():
        files.append((key, (None, value)))

    # Add the actual file data
    files.append(('file', (str(imagefile), imagefile.read_bytes())))

    # Perform the POST to S3
    # Note: No 'headers=headers' here; requests handles the Content-Type for multipart
    r = requests.post(url, files=files, timeout=TIMEOUT)

    print("Posted to S3. Result: ", r.status_code)
    if r.status_code >= 400:
        print("Error:", r.text)
