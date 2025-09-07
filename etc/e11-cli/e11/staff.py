"""
e11 staff commands.
"""

import os
import e11.e11core.ssh  as ssh

def enabled():
    return os.getenv('E11_STAFF','0')[0:1].upper() in ['Y','T','1']

def do_check_access(args):
    print("check ",args.host)
    ssh.configure(args.host, key_filename=args.keyfile)
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
