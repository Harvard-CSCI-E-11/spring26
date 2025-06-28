#!/usr/bin/env python3
import argparse
import logging
import sys

import boto3
from botocore.exceptions import ClientError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

def normalize(name):
    """Ensure name ends with a single trailing dot."""
    name = name.strip()
    if not name.endswith('.'):
        name += '.'
    return name

def get_hosted_zone_id(client, domain):
    """
    Find the hosted zone ID for a given domain name by paginating
    list_hosted_zones (which *is* pageable).
    """
    domain = normalize(domain)
    paginator = client.get_paginator('list_hosted_zones')
    for page in paginator.paginate():
        for zone in page.get('HostedZones', []):
            if normalize(zone['Name']) == domain:
                zone_id = zone['Id'].split('/')[-1]
                logger.info("Found hosted zone %s for domain %s", zone_id, domain)
                return zone_id
    logger.error("Hosted zone for domain %s not found", domain)
    sys.exit(1)

def list_a_records(client, zone_id):
    """Yield all A-type record sets in the given hosted zone."""
    paginator = client.get_paginator('list_resource_record_sets')
    for page in paginator.paginate(HostedZoneId=zone_id):
        for rr in page.get('ResourceRecordSets', []):
            if rr.get('Type') == 'A':
                yield {
                    'Name': normalize(rr['Name']),
                    'TTL': rr.get('TTL'),
                    'Records': [r['Value'] for r in rr.get('ResourceRecords', [])]
                }

def delete_records(client, zone_id, to_delete):
    """Submit a ChangeBatch to delete the given record-sets."""
    if not to_delete:
        logger.info("No records to delete.")
        return

    changes = []
    for rr in to_delete:
        change = {
            'Action': 'DELETE',
            'ResourceRecordSet': {
                'Name': rr['Name'],
                'Type': 'A',
                'TTL': rr['TTL'],
                'ResourceRecords': [{'Value': v} for v in rr['Records']]
            }
        }
        changes.append(change)

    batch = {'Changes': changes}
    logger.info("Submitting delete batch with %d record(s)", len(changes))
    try:
        resp = client.change_resource_record_sets(
            HostedZoneId=zone_id,
            ChangeBatch=batch
        )
        logger.info("Change submitted: %s", resp['ChangeInfo']['Id'])
    except ClientError as e:
        logger.error("Failed to delete records: %s", e)
        sys.exit(1)

def main():
    p = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                description="List and optionally delete Route 53 A records not on a keep-list." )
    p.add_argument('--domain', default='csci-e-11.org',
                   help="Domain name (must match hosted zone)")
    p.add_argument('--keep', default='keep-names.txt',
                   help="Path to file listing record names to keep (one per line)")
    p.add_argument('--delete', '-d', action='store_true',
                   help="Actually delete records not in keep-list. Otherwise dry‐run.")
    args = p.parse_args()

    # Read and normalize keep-list
    try:
        with open(args.keep, 'r') as f:
            keep_names = {normalize(line) for line in f if line.strip()}
    except IOError as e:
        logger.error("Unable to read keep-list file %s: %s", args.keep, e)
        sys.exit(1)

    client = boto3.Session(profile_name='fas').client('route53')
    zone_id = get_hosted_zone_id(client, args.domain)

    all_a = list(list_a_records(client, zone_id))
    if not all_a:
        logger.info("No A records found in zone %s", zone_id)
        return

    logger.info("Found %d A records:", len(all_a))
    for rr in all_a:
        logger.info("  %s → %s", rr['Name'], ', '.join(rr['Records']))

    # Filter out those we must keep
    to_delete = [rr for rr in all_a if rr['Name'] not in keep_names]

    if not to_delete:
        logger.info("All A records are in the keep-list. Nothing to delete.")
        return

    for rr in to_delete:
        logger.warning("  will delete %s", rr['Name'])
    logger.warning("records to delete: %d", len(to_delete))

    if args.delete:
        delete_records(client, zone_id, to_delete)
    else:
        logger.info("Dry run only. Rerun with --delete to remove them.")

if __name__ == '__main__':
    main()
