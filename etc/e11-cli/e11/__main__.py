#!/usr/bin/env python3.12
"""
The CSCI E-11 e11 program.
Note that we use python3.12 because that's what's installed on ubuntu 24.04
"""
import argparse
import sys
import logging
import os
import shutil
import subprocess
import json
from os.path import join # ,abspath,dirname
import dns
import dns.resolver
import dns.reversename

import requests

from email_validator import validate_email, EmailNotValidError

from . import staff
from .support import config_path,authorized_keys_path,bot_access_check,get_config,get_ipaddr,on_ec2,get_instanceId,REPO_YEAR,DEFAULT_TIMEOUT

from e11.e11core.constants import GRADING_TIMEOUT
from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core.loader import discover_and_run
from e11.e11core.render import print_summary
from e11.e11core.doctor import run_doctor
from e11.e11core.utils import get_logger

# because of our argument processing, args is typically given and frequently not used.
# pylint: disable=unused-argument, disable=invalid-name

__version__ = '0.1.0'
API_ENDPOINT = 'https://csci-e-11.org/api/v1'

logging.basicConfig(format='%(asctime)s  %(filename)s:%(lineno)d %(levelname)s: %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Student properties
STUDENT='student'
STUDENT_EMAIL='email'
STUDENT_NAME='name'
INSTANCE_IPADDR='ipaddr'
INSTANCE_ID='instanceId'
COURSE_KEY='course_key'
COURSE_KEY_LEN=6
STUDENT_ATTRIBS = [STUDENT_NAME,STUDENT_EMAIL,COURSE_KEY,INSTANCE_IPADDR,INSTANCE_ID]

UPDATE_CMDS=f"""cd /home/ubuntu/{REPO_YEAR}
git stash
git pull
(cd etc/e11; pipx install . --force)
git stash apply
"""

def do_version(args):
    print("version",__version__)

def do_access_on(args):
    if bot_access_check():
        logger.info("Course admins already has access...")
    else:
        logger.info("Granting access to course admins...")
        with authorized_keys_path.open('a') as f:
            f.write( cscie11_bot_key() )

def do_access_off(args):
    if not bot_access_check():
        logger.info("Course admins do not have access.")
    else:
        logger.info("Revoking access from course admins...")
        key = cscie11_bot_key()
        newpath = authorized_keys_path().with_suffix('.new')
        with authorized_keys_path().open('r') as infile:
            with newpath.open('w') as outfile:
                for line in infile:
                    if line==key:
                        continue
                    outfile.write(line)
        newpath.replace(authorized_keys_path())

def do_access_check(args):
    logger.info("Checking access status for %s:",get_ipaddr())
    if bot_access_check():
        logger.info("CSCI E-11 Course Admin HAS ACCESS to this instance.")
    else:
        logger.info("CSCI E-11 Course Admin DOES NOT HAVE ACCESS to this instance.")

def do_config(args):
    cp = get_config()
    for attrib in STUDENT_ATTRIBS:
        while True:
            buf = input(f"{attrib}: [{cp[STUDENT].get(attrib,'')}] ")
            if buf:
                cp[STUDENT][attrib] = buf
            if cp[STUDENT].get(attrib,'') != '':
                break
    with open(CONFIG_FILE_NAME,'w') as f:
        print(f"Writing configuration to {CONFIG_FILE_NAME}:")
        cp.write(sys.stdout)
        cp.write(f)
        print("\nDone!")

def do_register(args):
    errors = 0
    cp = get_config()
    for at in STUDENT_ATTRIBS:
        if at not in cp[STUDENT]:
            print(f"ERROR: {at} not in configuration file.")
            errors += 1
        if cp[STUDENT][at] == "":
            print(f"ERROR: {at} is empty in configuration file.")
            errors += 1
    # Check the IP address
    ipaddr = cp[STUDENT].get(INSTANCE_IPADDR)
    if ipaddr != get_ipaddr():
        print(f"ERROR: This instance does not have the public IP address {ipaddr}.")
        errors += 1
    email = cp[STUDENT][STUDENT_EMAIL]
    try:
        emailinfo = validate_email(email, check_deliverability=False)
        email = emailinfo.email
    except EmailNotValidError as e:
        print(f"ERROR: '{email}' is not a valid email address: {e}")
        errors += 1
    instanceId = get_instanceId()
    if cp[STUDENT].get(INSTANCE_ID) != instanceId:
        print(f"ERROR: '{instanceId}' is not the instanceId of this EC2 instance.")
        errors += 1

    name = cp[STUDENT].get(STUDENT_NAME,"").strip()
    if len(name)<3 or name.count(" ")<1:
        print(f"ERROR: '{name}' is not a valid student name.")
        errors += 1

    course_key = cp[STUDENT].get(COURSE_KEY,"").strip()
    if len(course_key)!=COURSE_KEY_LEN:
        print(f"ERROR: course_key '{course_key}' is not valid")

    if errors>0:
        print(f"\n{errors} error{'s' if errors!=1 else ''} in configuration file.")
        print("Please re-run 'e11 config' and then re-run 'e11 config'.")
        sys.exit(0)

    print("Attempting to register...")

    # write to the S3 storage with the email address as the key
    data = {'action':'register', 'registration' : dict(cp[STUDENT])}

    r = requests.post(API_ENDPOINT, json=data, timeout=DEFAULT_TIMEOUT)
    if not r.ok:
        print("Registration failed: ",r.text)
    else:
        print("Registered!")
        print("If you do not receive a message in 60 seconds, check your email address and try again.")


def do_grade(args):
    print("Requesting server to grade...")
    cp = get_config()
    r = requests.post(API_ENDPOINT, json={'action':'grade',
                                          'grade': dict(cp[STUDENT])},
                      timeout = GRADING_TIMEOUT+1 ) # wait for 1 second longer than server waits
    result = r.json()
    print("Response:")
    print_summary(result['summary'], verbose=getattr(args, "verbose", False))
    if args.debug:
        print(json.dumps(r.json(),indent=4))
    sys.exit(0 if not result['summary']["fails"] else 1)


def do_status(_):
    ipaddr = get_ipaddr()
    print("Instance IP address: ", ipaddr)
    try:
        raddr = dns.resolver.resolve(dns.reversename.from_address(ipaddr), "PTR")[0]
        print("Reverse DNS: ", raddr)
    except dns.resolver.NXDOMAIN:
        print("No reverse DNS for",ipaddr)
    print("\nE11 config variables from /home/ubuntu/e11-config.ini:")
    cp = get_config()
    for at in cp[STUDENT]:
        print(f"{at} = {cp[STUDENT][at]}")


def do_update(_):
    repo_dir = f"/home/ubuntu/{REPO_YEAR}"
    if not os.path.exists(repo_dir):
        print(f"{REPO_YEAR} does not exist",file=sys.stderr)
        sys.exit(1)
    os.chdir(repo_dir)
    for cmd in UPDATE_CMDS.split('\n'):
        print(f"$ {cmd}")
        os.system(cmd)

def do_check(args):
    ctx = build_ctx(args.lab)          # args.lab like 'lab3'
    chdir_to_lab(ctx)
    summary = discover_and_run(ctx)
    print_summary(summary, verbose=getattr(args, "verbose", False))
    sys.exit(0 if not summary["fails"] else 1)

def do_doctor(_):
    run_doctor()

def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access')
    parser.add_argument("--debug", help='Run in debug mode', action='store_true')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # primary commands
    subparsers.add_parser('config', help='Config E11 student variables').set_defaults(func=do_config)
    subparsers.add_parser('register', help='Register this instance').set_defaults(func=do_register)
    subparsers.add_parser('status', help='Report status of the e11 system.').set_defaults(func=do_status)
    subparsers.add_parser('update', help='Update the e11 system').set_defaults(func=do_update)
    subparsers.add_parser('version', help='Update the e11 system').set_defaults(func=do_version)
    subparsers.add_parser('doctor', help='Self-test the system').set_defaults(func=do_doctor)
    parser.add_argument('--force', help='Run even if not on ec2',action='store_true')

    # e11 access [on|off|check]
    access_parser = subparsers.add_parser('access', help='Enable or disable access')
    access_subparsers = access_parser.add_subparsers(dest='action')

    access_subparsers.add_parser('on', help='Enable SSH access').set_defaults(func=do_access_on)
    access_subparsers.add_parser('off', help='Disable SSH access').set_defaults(func=do_access_off)
    access_subparsers.add_parser('check', help='Report SSH access').set_defaults(func=do_access_check)

    # e11 grade [lab]
    grade_parser = subparsers.add_parser('grade', help='Request lab grading (run from course server)')
    grade_parser.add_argument(dest='lab', help='Lab to grade')
    grade_parser.set_defaults(func=do_grade)

    # e11 check [lab]
    check_parser = subparsers.add_parser('check', help='Check a lab (run from your instance)')
    check_parser.add_argument(dest='lab', help='Lab to check')
    check_parser.set_defaults(func=do_check)

    # e11 staff commands
    if staff.enabled():
        staff.add_parsers(parser,subparsers)


    args = parser.parse_args()
    if not on_ec2() and not staff.enabled():
        if args.force:
            print("WARNING: This should be run on EC2")
        else:
            print("ERROR: This must be run on EC2")
            sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
