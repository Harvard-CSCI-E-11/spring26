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
import configparser
import requests
import boto3
import subprocess
from os.path import join,abspath,dirname

from email_validator import validate_email, EmailNotValidError
import dns
import boto3
import requests
from dns import resolver,reversename

from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core.loader import discover_and_run
from e11.e11core.render import print_summary
from e11.e11core.doctor import run_doctor

REPO_YEAR='spring26'
REGISTRATION_ENDPOINT = 'https://csci-e-11.org/register'
__version__ = '0.1.0'

logging.basicConfig(format='%(asctime)s  %(filename)s:%(lineno)d %(levelname)s: %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HOME_DIR = os.getenv("HOME")
AUTHORIZED_KEYS_FILE = join( HOME_DIR , ".ssh", "authorized_keys")
ETC_DIR = join( HOME_DIR, REPO_YEAR, "etc")
if not os.path.exists(ETC_DIR):
    ETC_DIR = join( HOME_DIR, "gits", "csci-e-11", "etc")

CONFIG_FILE = join( HOME_DIR, 'e11-config.ini')
CSCIE_BOT_KEYFILE = join(ETC_DIR, 'csci-e-11-bot.pub')
# Student properties
STUDENT='student'
STUDENT_EMAIL='email'
STUDENT_NAME='name'
STUDENT_HUID='huid'
INSTANCE_IPADDR='ipaddr'
INSTANCE_ID='instanceId'
COURSE_KEY='course_key'
STUDENT_ATTRIBS = [STUDENT_NAME,STUDENT_EMAIL,STUDENT_HUID,INSTANCE_IPADDR,INSTANCE_ID]
COURSE_KEY_ATTRIBS = [COURSE_KEY]

def do_version(args):
    print("version",__version__)

def get_config():
    """Return the config file"""
    cp = configparser.ConfigParser()
    try:
        with open(CONFIG_FILE,'r') as f:
            cp.read_file(f)
    except FileNotFoundError:
        pass
    if STUDENT not in cp:
        cp.add_section(STUDENT)
    return cp

def get_ipaddr():
    r = requests.get('https://checkip.amazonaws.com')
    return r.text.strip()

def on_ec2():
    """https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/identify_ec2_instances.html"""
    r = subprocess.run(['sudo','-n','dmidecode','--string','system-uuid'],
                       encoding='utf8',
                       capture_output=True)
    return r.stdout.startswith('ec2')

def get_instanceId():
    token_url = "http://169.254.169.254/latest/api/token"
    headers = {"X-aws-ec2-metadata-token-ttl-seconds": "21600"}
    response = requests.put(token_url, headers=headers, timeout=1)
    response.raise_for_status()
    token = response.text
    metadata_url = "http://169.254.169.254/latest/meta-data/instance-id"
    headers = {"X-aws-ec2-metadata-token": token}
    response = requests.get(metadata_url, headers=headers, timeout=1)
    response.raise_for_status()
    return response.text

def cscie11_bot_key():
    with open(CSCIE_BOT_KEYFILE, 'r') as f:
        key = f.read()
        assert key.count("\n")==1 and key.endswith("\n")
        return key

def do_access_on(args):
    logger.info("Granting access to course admins...")
    with open(AUTHORIZED_KEYS_FILE,'a') as f:
        f.write(cscie11_bot_key())

def do_access_off(args):
    key = cscie11_bot_key()
    logger.info("Revoking access...")
    with open(AUTHORIZED_KEYS_FILE,'r') as infile:
        with open(AUTHORIZED_KEYS_FILE+'.new', 'w') as outfile:
            for line in infile:
                if line==key:
                    continue
                outfile.write(line)
    shutil.move(AUTHORIZED_KEYS_FILE+'.new', AUTHORIZED_KEYS_FILE)

def do_access_check(args):
    logger.info(f"Checking access status for {get_ipaddr()}:")
    key = cscie11_bot_key()
    with open(AUTHORIZED_KEYS_FILE,'r') as f:
        for line in f:
            if line == key:
                logger.info("CSCI E-11 Course Admin HAS ACCESS to this instance.")
                return
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
    with open(CONFIG_FILE,'w') as f:
        cp.write(f)


def do_set_course_key(args):
    cp = get_config()
    for attrib in COURSE_KEY_ATTRIBS:
        while True:
            buf = input(f"{attrib}: [{cp[STUDENT].get(attrib,'')}] ")
            if buf:
                cp[STUDENT][attrib] = buf
            if cp[STUDENT].get(attrib,'') != '':
                break
    with open(CONFIG_FILE,'w') as f:
        cp.write(f)


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
    ipaddr = cp[STUDENT][INSTANCE_IPADDR]
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
    if cp[STUDENT][INSTANCE_ID] != instanceId:
        print(f"ERROR: '{instanceId}' is not the instanceId of this EC2 instance.")
        errors += 1

    huid = cp[STUDENT][STUDENT_HUID]
    if not huid.isdigit():
        print(f"ERROR: '{huid}' contains non-digit characters and is not a valid HUDI.")
        errors += 1

    name = cp[STUDENT][STUDENT_NAME].strip()
    if len(name)<3 or name.count(" ")<1:
        print(f"ERROR: '{name}' is not a valid student name.")
        errors += 1

    if errors>0:
        print(f"\n{errors} error{'s' if errors!=1 else ''} in configuration file.")
        print("Please re-run 'e11 config' and then re-run 'e11 config'.")
        exit(0)

    print("Attempting to register...")

    # write to the S3 storage with the email address as the key
    data = {'action':'register',
            'registration' : {
                'huid': huid,
                'ipaddr': ipaddr,
                'email' : email,
                'name': name }
            }
    r = requests.post(REGISTRATION_ENDPOINT, json=data)
    if not r.ok:
        print("Registration failed: ",r.text)
    else:
        print("Registered!")
        print("If you do not receive a message in 60 seconds, check your email address and try again.")



def do_status(args):
    ipaddr = get_ipaddr()
    print("Instance IP address: ", ipaddr)
    try:
        raddr = resolver.resolve(reversename.from_address(ipaddr), "PTR")[0]
        print("Reverse DNS: ", raddr)
    except dns.resolver.NXDOMAIN:
        print("No reverse DNS for",ipaddr)
    print("\nE11 config variables from /home/ubuntu/e11-config.ini:")
    cp = get_config()
    for at in cp[STUDENT]:
        print(f"{at} = {cp[STUDENT][at]}")


UPDATE_CMDS=f"""cd /home/ubuntu/{REPO_YEAR}
git stash
git pull
(cd etc/e11; pipx install . --force)
git stash apply
"""

def do_update(args):
    repo_dir = f"/home/ubuntu/{REPO_YEAR}"
    if not os.path.exists(repo_dir):
        print(f"{REPO_YEAR} does not exist",file=sys.stderr)
        exit(1)
    os.chdir(repo_dir)
    for cmd in UPDATE_CMDS.split('\n'):
        print(f"$ {cmd}")
        os.system(cmd)

def do_grade(args):
    print("Attempting to grade...")
    ctx = build_ctx(args.lab)
    chdir_to_lab(ctx)
    # local preview (optional): comment out if you want server-only
    summary = discover_and_run(ctx)
    print_summary(summary, verbose=getattr(args, "verbose", False))
    # TODO: POST to grader API with HMAC if desired; for now, exit with local status
    sys.exit(0 if not summary["fails"] else 1)


def do_check(args):
    ctx = build_ctx(args.lab)          # args.lab like 'lab3'
    chdir_to_lab(ctx)
    summary = discover_and_run(ctx)
    print_summary(summary, verbose=getattr(args, "verbose", False))
    sys.exit(0 if not summary["fails"] else 1)

    print("Checking not implemented yet")

def do_doctor(args):
    print("Doctor not implemented yet")

def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # primary commands
    subparsers.add_parser('config', help='Config E11 student variables').set_defaults(func=do_config)
    subparsers.add_parser('set-course-key', help='Set the course key that you were provided with by email').set_defaults(func=do_set_course_key)
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
    grade_parser = subparsers.add_parser('grade', help='Grade a lab')
    grade_parser.add_argument(dest='lab', help='Lab to grade')
    grade_parser.set_defaults(func=do_grade)

    # e11 check [lab]
    check_parser = subparsers.add_parser('check', help='Check a lab')
    check_parser.add_argument(dest='lab', help='Lab to check')
    check_parser.set_defaults(func=do_check)


    args = parser.parse_args()
    if not on_ec2():
        if args.force:
            print("WARNING: This should be run on EC2")
        else:
            print("ERROR: This must be run on EC2")
            exit(1)
    args.func(args)


if __name__ == "__main__":
    main()
