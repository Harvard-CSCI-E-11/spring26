#!/usr/bin/env python3.12
"""
The CSCI E-11 e11 program.
Note that we use python3.12 because that's what's installed on ubuntu 24.04
"""
import argparse
import sys
import os
import json
import pathlib

import dns
import dns.resolver
import dns.reversename

import requests

from email_validator import validate_email, EmailNotValidError

from . import staff
from .support import authorized_keys_path,bot_access_check,bot_pubkey,config_path,get_public_ip,on_ec2,get_instanceId,REPO_YEAR,DEFAULT_TIMEOUT,get_config

from .e11core.constants import GRADING_TIMEOUT
from .e11core.context import build_ctx, chdir_to_lab
from .e11core.render import print_summary
from .e11core.utils import get_logger
from .e11core import grader

from .doctor import run_doctor


# because of our argument processing, args is typically given and frequently not used.
# pylint: disable=unused-argument, disable=invalid-name

__version__ = '0.1.0'
API_ENDPOINT = 'https://csci-e-11.org/api/v1'
STAGE_ENDPOINT = 'https://stage.csci-e-11.org/api/v1'

logger = get_logger()

# Student properties
STUDENT='student'
STUDENT_EMAIL='email'
STUDENT_PREFERRED_NAME='preferred_name'
INSTANCE_PUBLIC_IP='public_ip'
INSTANCE_ID='instanceId'
COURSE_KEY='course_key'
COURSE_KEY_LEN=6
STUDENT_ATTRIBS = [STUDENT_PREFERRED_NAME,STUDENT_EMAIL,COURSE_KEY,INSTANCE_PUBLIC_IP,INSTANCE_ID]

UPDATE_CMDS=f"""cd /home/ubuntu/{REPO_YEAR}
git stash
git pull
(cd etc/e11-cli; pipx install . --force)
git stash apply
"""

def endpoint(args):
    if args.stage is True:
        return STAGE_ENDPOINT
    return API_ENDPOINT

def do_version(args):
    print("version",__version__)

def do_access_on(args):
    if bot_access_check():
        logger.info("Course admins already has access...")
    else:
        logger.info("Granting access to course admins...")
        with authorized_keys_path().open('a') as f:
            f.write( bot_pubkey() )
    # Be sure permissions are set properly
    authorized_keys_path().chmod(0o600)
    authorized_keys_path().parent.chmod(0o700)
    authorized_keys_path().home().chmod(0o750)

def do_access_off(args):
    if not bot_access_check():
        logger.info("Course admins do not have access.")
    else:
        logger.info("Revoking access from course admins...")
        key = bot_pubkey()
        newpath = authorized_keys_path().with_suffix('.new')
        with authorized_keys_path().open('r') as infile:
            with newpath.open('w') as outfile:
                for line in infile:
                    if line==key:
                        continue
                    outfile.write(line)
        newpath.replace(authorized_keys_path())

def do_access_check(args):
    logger.info("Checking access status for %s:",get_public_ip())
    if bot_access_check():
        logger.info("CSCI E-11 Course Admin HAS ACCESS to this instance (based on .ssh/authorized_keys file).")
    else:
        logger.info("CSCI E-11 Course Admin DOES NOT HAVE ACCESS to this instance (based on .ssh/authorized_keys file).")

def do_config(args):
    cp = get_config()
    for attrib in STUDENT_ATTRIBS:
        while True:
            buf = input(f"{attrib}: [{cp[STUDENT].get(attrib,'')}] ")
            if buf:
                cp[STUDENT][attrib] = buf
            if cp[STUDENT].get(attrib,'') != '':
                break
    with config_path().open('w') as f:
        print(f"Writing configuration to {config_path()}:")
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
    public_ip = cp[STUDENT].get(INSTANCE_PUBLIC_IP)
    if public_ip != get_public_ip():
        print(f"ERROR: This instance does not have the public IP address {public_ip}.")
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

    preferred_name = cp[STUDENT].get(STUDENT_PREFERRED_NAME,"").strip()
    if len(preferred_name)==0:
        print(f"ERROR: '{preferred_name}' is not a valid student preferred name.")
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
    data = {'action':'register',
            'auth':{STUDENT_EMAIL:cp[STUDENT][STUDENT_EMAIL], COURSE_KEY:cp[STUDENT][COURSE_KEY]},
            'registration' : dict(cp[STUDENT])}

    r = requests.post(endpoint(args), json=data, timeout=DEFAULT_TIMEOUT)
    if not r.ok:
        print("Registration failed: ",r.text)
    else:
        print("Registered!")
        print("If you do not receive a message in 60 seconds, check your email address and try again.")


def do_access_check_dashboard(args):
    print("Checking dashboard to see if it has access")
    ep = endpoint(args)
    cp = get_config()
    r = requests.post(ep, json={'action':'check-access',
                                'auth':{STUDENT_EMAIL:cp[STUDENT][STUDENT_EMAIL], COURSE_KEY:cp[STUDENT][COURSE_KEY]}},
                      timeout = GRADING_TIMEOUT+5 )
    if r.ok:
        print(f"Response from dashboard: {r.json()['message']}")
    else:
        print(f"dashboard returned error: {r} {r.text}")


def do_grade(args):
    lab = args.lab
    if args.direct:
        if not args.identity:
            print("--direct requires [-i | --identity | --pkey_pem ]")
            sys.exit(1)
        cp = get_config()
        print(f"Grading Direct: {cp['student']['email']}@{cp['student']['public_ip']} for {lab}")
        summary = grader.grade_student_vm(cp['student']['email'],cp['student']['public_ip'],lab,pkey_pem=args.identity.read_text())
        (_,body) = grader.create_email(summary)
        print(body)
        return

    ep = endpoint(args)
    print(f"Requesting {ep} to grade {lab}...")
    cp = get_config()
    r = requests.post(ep, json={'action':'grade',
                                'auth':{STUDENT_EMAIL:cp[STUDENT][STUDENT_EMAIL], COURSE_KEY:cp[STUDENT][COURSE_KEY]},
                                'lab': lab},
                      timeout = GRADING_TIMEOUT+5 ) # wait for 5 seconds longer than server waits
    result = r.json()
    if not r.ok:
        print("Error: ",r.text)
        sys.exit(1)
    print_summary(result['summary'], verbose=getattr(args, "verbose", False))
    if args.debug:
        print(json.dumps(r.json(),indent=4))
    try:
        print_summary(result['summary'], verbose=getattr(args, "verbose", False))
    except KeyError:
        print(f"Invalid response from server:\n{json.dumps(result,indent=4)}")
        sys.exit(1)
    sys.exit(0 if not result['summary']["fails"] else 1)


def do_status(_):
    public_ip = get_public_ip()
    print("Instance Public IP address: ", public_ip)
    try:
        raddr = dns.resolver.resolve(dns.reversename.from_address(public_ip), "PTR")[0]
        print("Reverse DNS: ", raddr)
    except dns.resolver.NXDOMAIN:
        print("No reverse DNS for",public_ip)
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
    summary = grader.discover_and_run(ctx)
    print_summary(summary, verbose=getattr(args, "verbose", False))
    sys.exit(0 if not summary["fails"] else 1)

def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access')
    parser.add_argument("--debug", help='Run in debug mode', action='store_true')
    parser.add_argument("--stage", help='Use stage API', action='store_true')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # primary commands
    subparsers.add_parser('config', help='Config E11 student variables').set_defaults(func=do_config)
    subparsers.add_parser('register', help='Register this instance').set_defaults(func=do_register)
    subparsers.add_parser('status', help='Report status of the e11 system.').set_defaults(func=do_status)
    subparsers.add_parser('update', help='Update the e11 system').set_defaults(func=do_update)
    subparsers.add_parser('version', help='Update the e11 system').set_defaults(func=do_version)
    subparsers.add_parser('doctor', help='Self-test the system').set_defaults(func=run_doctor)
    parser.add_argument('--force', help='Run even if not on ec2',action='store_true')

    # e11 access [on|off|check]
    access_parser = subparsers.add_parser('access', help='Enable or disable access')
    access_subparsers = access_parser.add_subparsers(dest='action')

    access_subparsers.add_parser('on', help='Enable SSH access').set_defaults(func=do_access_on)
    access_subparsers.add_parser('off', help='Disable SSH access').set_defaults(func=do_access_off)
    access_subparsers.add_parser('check', help='Report SSH access').set_defaults(func=do_access_check)
    access_subparsers.add_parser('check-dashboard', help='Report SSH access').set_defaults(func=do_access_check_dashboard)

    # e11 grade [lab]
    grade_parser = subparsers.add_parser('grade', help='Request lab grading (run from course server)')
    grade_parser.add_argument(dest='lab', help='Lab to grade')
    grade_parser.add_argument('--verbose', help='print all details',action='store_true')
    grade_parser.add_argument('--direct', help='Instead of grading from server, grade from this system. Requires SSH access to target',action='store_true')
    grade_parser.add_argument('-i','--identity','--pkey_pem', help='Specify public key to use for direct grading',type=pathlib.Path)
    grade_parser.set_defaults(func=do_grade)

    # e11 check [lab]
    check_parser = subparsers.add_parser('check', help='Check a lab (run from your instance)')
    check_parser.add_argument(dest='lab', help='Lab to check')
    check_parser.set_defaults(func=do_check)

    # e11 staff commands
    if staff.enabled():
        staff.add_parsers(parser,subparsers)

    args = parser.parse_args()
    if not on_ec2():
        if args.command=='grade' and args.direct:
            pass
        elif staff.enabled():
            pass
        elif args.force:
            print("WARNING: This should be run on EC2")
        else:
            print("ERROR: This must be run on EC2")
            sys.exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
