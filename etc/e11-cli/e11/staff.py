"""
e11 staff commands.
"""

import os

def enabled():
    return os.getenv('E11_STAFF','0')[0:1].upper() in ['Y','T','1']

def do_check_access(args):
    print("check ",args.host)

def add_parsers(subparsers):
    ca = subparsers.add_parser('check-access', help='E11_STAFF: Check to see if we can access a host')
    ca.add_argument(dest='host', help='Host to check')
    ca.set_defaults(func=do_check_access)
