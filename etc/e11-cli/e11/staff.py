"""
e11 staff commands.
"""

import os
from .e11core.e11ssh import E11Ssh

def enabled():
    return os.getenv('E11_STAFF','0')[0:1].upper() in ['Y','T','1']

def do_check_access(args):
    print("Checking access to {args.host} from this host (not the lambda server)")
    with E11Ssh(args.host, key_filename=args.keyfile) as ssh:
        rc, out, err = ssh.exec("hostname")
        if rc!=0:
            print("rc=",rc)
        if out:
            print("out:\n",out)
        if err:
            print("err:\n",err)

def add_parsers(parser,subparsers):
    ca = subparsers.add_parser('check-access', help='E11_STAFF: Check to see if we can access a host')
    ca.add_argument(dest='host', help='Host to check')
    ca.set_defaults(func=do_check_access)
    parser.add_argument("--keyfile",help="SSH private ke file")
