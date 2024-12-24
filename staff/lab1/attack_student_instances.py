"""
This program reads the contents of the S3 bucket and attempts to log into each student machine.
"""
import os
import sys
import asyncio
import asyncssh
import boto3

S3_BUCKET = 'cscie-11'
S3_PREFIX = 'students/'
PROFILE = 'fas'

# Get the HIDDEN value
try:
    HIDDEN = os.environ["HIDDEN"]
except KeyError:
    print("Define environment variable HIDDEN prior to running this script",file=sys.stderr)
    exit(1)

class S3ObjectIterator:
    """Creates an iterator that returns the (s3url, content) of all s3 objects under a prefix"""
    def __init__(self, bucket_name, prefix, aws_region="us-east-1", profile_name=None):
        self.bucket_name = bucket_name
        self.prefix = prefix
        session = boto3.Session(profile_name=profile_name, region_name=aws_region)
        self.s3_client = session.client("s3")
        self.objects = self._get_object_list()

    def _get_object_list(self):
        # Fetch the list of objects under the specified prefix
        paginator = self.s3_client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket_name, Prefix=self.prefix):
            for obj in page.get("Contents", []):
                yield obj["Key"]

    def __iter__(self):
        return self

    def __next__(self):
        try:
            key = next(self.objects)
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            data = response["Body"].read().decode("utf-8")  # Assumes content is text
            bucket_key = f"s3://{self.bucket_name}/{key}"
            return bucket_key, data
        except StopIteration as exc:
            raise StopIteration from exc

################################################################
## Code to attack multiple machines in parallel

async def connect_and_run(host, username, password, command):
    """co-routine to connect to the host and try to execute a command"""
    try:
        async with asyncssh.connect(host,
                                    username=username,
                                    password=password,
                                    known_hosts=None) as conn:
            result = await conn.run(command, check=True)
            return f"{host}: {result.stdout.strip()}"
    except Exception as e:
        return f"{host}: Failed with error: {e}"

async def run_on_all_machines(hosts):
    """co-routine to try to connect to all of the hosts in the provided lists"""
    password = '***'
    command  = 'hostname'
    tasks = [
        connect_and_run(host, f'{HIDDEN}-{host}', password, command) for host in hosts
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results


if __name__ == "__main__":
    hosts = []
    for urn, content in S3ObjectIterator(S3_BUCKET, S3_PREFIX, profile_name=PROFILE):
        print(f"URN: {urn}")
        print(f"Content: {content}")
        (account_id, ipaddr, email, name) = content.strip().split(',')
        hosts.append(ipaddr.strip())
    results = asyncio.run(run_on_all_machines(hosts))
    for r in results:
        print(r)
