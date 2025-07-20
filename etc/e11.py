#!/usr/bin/env python3.11
"""
The CSCI E-11 e11 program.
"""
import argparse
import sys

def do_access_on(args):
    print("[INFO] Granting access...")
    # Example: add your SSH key
    # subprocess.run(['...'])

def do_access_off(args):
    print("[INFO] Revoking access...")
    # Example: remove your SSH key

def do_status_check(args):
    print("[INFO] Checking access status...")
    # Example: check authorized_keys

def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # e11 access [on|off]
    access_parser = subparsers.add_parser('access', help='Enable or disable access')
    access_subparsers = access_parser.add_subparsers(dest='action', required=True)

    access_on = access_subparsers.add_parser('on', help='Enable SSH access')
    access_on.set_defaults(func=do_access_on)

    access_off = access_subparsers.add_parser('off', help='Disable SSH access')
    access_off.set_defaults(func=do_access_off)

    # e11 status check
    status_parser = subparsers.add_parser('status', help='Check access status')
    status_subparsers = status_parser.add_subparsers(dest='action', required=True)

    status_check = status_subparsers.add_parser('check', help='Check SSH status')
    status_check.set_defaults(func=do_status_check)

    try:
        args = parser.parse_args()
        args.func(args)
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
