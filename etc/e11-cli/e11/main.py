#!/usr/bin/env python3.12
"""
The CSCI E-11 e11 program.
Note that we use python3.12 because that's what's installed on ubuntu 24.04
"""
import argparse
import importlib
import inspect
import json
import os
import re
import sys

import dns
import dns.resolver
import dns.reversename

import requests

from email_validator import validate_email, EmailNotValidError

from . import staff
from .support import authorized_keys_path,bot_access_check,bot_pubkey,config_path,get_public_ip,on_ec2,get_instanceId,REPO_YEAR,DEFAULT_TIMEOUT,get_config

from .e11core.constants import GRADING_TIMEOUT, API_ENDPOINT, STAGE_ENDPOINT, COURSE_KEY_LEN, LAB_MAX
from .e11core.context import build_ctx, chdir_to_lab
from .e11core.grader import collect_tests_in_definition_order,print_summary
from .e11core.utils import get_logger,smash_email
from .e11core import grader

from .doctor import run_doctor


# because of our argument processing, args is typically given and frequently not used.
# pylint: disable=unused-argument, disable=invalid-name

__version__ = '0.2.2'

logger = get_logger()

# Student properties
STUDENT='student'
STUDENT_EMAIL='email'
STUDENT_PREFERRED_NAME='preferred_name'
INSTANCE_PUBLIC_IP='public_ip'
INSTANCE_ID='instanceId'
COURSE_KEY='course_key'
STUDENT_ATTRIBS = [STUDENT_PREFERRED_NAME,STUDENT_EMAIL,COURSE_KEY,INSTANCE_PUBLIC_IP,INSTANCE_ID]
ANSWERS = {"lab1":['e11-attacker'],
           "lab4":['api_key','api_secret_key'],
           "lab5":['api_key','api_secret_key'],
           "lab6":['api_key','api_secret_key']}


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
    print(f"E11 local version: {__version__}")
    ep = endpoint(args)
    r = requests.post(ep, json={'action':'version'},timeout=5)
    data = r.json()
    if data['error']:
        print(f"Error attempting to get server version: {data}")
    else:
        print(f"E11 server version: {data['version']} (deployed {data['deployment_timestamp']})")
        if __version__.split() < data['version'].split():
            print("Update to current version with: `e11 update`")


################################################################

def fix_access_permissions():
    authorized_keys_path().chmod(0o600)
    authorized_keys_path().parent.chmod(0o700)
    authorized_keys_path().home().chmod(0o750)

def do_access_on(args):
    if bot_access_check():
        logger.info("Course admins already has access...")
    else:
        logger.info("Granting access to course admins...")
        with authorized_keys_path().open('a') as f:
            f.write( bot_pubkey() )
    fix_access_permissions()

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
    fix_access_permissions()

def do_access_check(args):
    logger.debug("Checking access status for %s:",get_public_ip())
    fix_access_permissions()
    if bot_access_check():
        print("CSCI E-11 Course admin and grader HAVE ACCESS to this instance.")
    else:
        print("CSCI E-11 Course admin and grader DO NOT HAVE ACCESS to this instance.")

def do_access_check_dashboard(args):
    fix_access_permissions()
    print("Checking dashboard to see if it has access for an authenticated user.")
    ep = endpoint(args)
    cp = get_config()
    r = requests.post(ep, json={'action':'check-access',
                                'auth':{STUDENT_EMAIL:cp[STUDENT][STUDENT_EMAIL], COURSE_KEY:cp[STUDENT][COURSE_KEY]}},
                      timeout = GRADING_TIMEOUT+5 )
    if r.ok:
        print(f"Response from dashboard: {r.json()['message']}")
    else:
        print(f"dashboard returned error: {r} {r.text}")

def do_access_check_me(args):
    fix_access_permissions()
    print("Checking dashboard to see if it has access for this public IP address")
    ep = endpoint(args)
    r = requests.post(ep, json={'action':'check-me'}, timeout = GRADING_TIMEOUT+5 )
    if r.ok:
        print(f"Message from dashboard: {r.json()['message']}")
        print("Full response:\n",json.dumps(r.json(),indent=4))
    else:
        print(f"dashboard returned error: {r} {r.text}")


################################################################

def get_answers(cp,section_name,attribs):
    section = cp[section_name]
    for attrib in attribs:
        while True:
            buf = input(f"{attrib}: [{section.get(attrib,'')}] ")
            if buf:
                section[attrib] = buf
            if section.get(attrib,'') != '':
                break

def write_config(cp):
    with config_path().open('w') as f:
        print(f"Writing configuration to {config_path()}:")
        cp.write(sys.stdout)
        cp.write(f)
        print("\nDone!")

def do_config(args):
    cp = get_config()
    if args.get and args.section and args.key:
        val = cp[args.section][args.key]
        if args.key=='email' and args.smash:
            val = smash_email(val)
        print(val)
        return
    if args.section and args.key and args.setvalue:
        if args.section not in cp:
            cp.add_section(args.section)
        cp[args.section][args.key] = args.setvalue
    else:
        get_answers(cp,STUDENT,STUDENT_ATTRIBS)
    write_config(cp)

def do_answer(args):
    cp = get_config()
    m = re.search("^lab[0-9]$",args.lab)
    if not m:
        print("usage: e11 answer <labn>")
        sys.exit(1)
    if args.lab not in ANSWERS:
        print(f"There are no additional answers required for lab {args.lab}")
        return
    if args.lab not in cp:
        cp.add_section(args.lab)
    get_answers(cp, args.lab, ANSWERS[args.lab])
    write_config(cp)

# pylint: disable=too-many-statements
def do_register(args):
    errors = 0
    verbose = not args.quiet
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
        if args.fixip:          # silently fix the IP address
            cp.set(STUDENT,INSTANCE_PUBLIC_IP,get_public_ip())
            write_config(cp)
        else:
            print(f"ERROR: This instance does not have the public IP address {public_ip}.")
            errors += 1
    email = cp[STUDENT][STUDENT_EMAIL]
    try:
        validate_email(email, check_deliverability=False)
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
            'verbose':verbose,
            'registration' : dict(cp[STUDENT])}

    MAX_RETRIES = 3
    for n in range(1,MAX_RETRIES+1):
        try:
            r = requests.post(endpoint(args), json=data, timeout=DEFAULT_TIMEOUT)
            if not r.ok:
                print("Registration failed: ",r.text)
                sys.exit(1)
        except TimeoutError:
            if n==MAX_RETRIES:
                print("Retries reached. Please contact course support and try again later")
                sys.exit(1)
            print(f"retrying... {n}/{MAX_RETRIES}")

    if verbose:
        print("Registered!")
        print("Message: ",r.json()['message'])
        print("You should also receive an email within 60 seconds. If not, please check your email address and try again.")


def do_grade(args):
    lab = args.lab
    if args.direct:
        cp = get_config()
        email     = cp['student']['email']
        public_ip = args.direct
        if not args.identity:
            print("--direct requires [-i | --identity | --pkey_pem ]",file=sys.stderr)
            sys.exit(1)
        if args.identity.endswith(".pub"):
            args.identity = args.identity.replace(".pub","")
        print(f"Grading Direct: {email}@{public_ip} for {lab} with SSH key {args.identity}")
        summary = grader.grade_student_vm(email,public_ip,lab,key_filename=args.identity)
        if summary.get('error'):
            print("summary error:",summary)
            sys.exit(1)
        (_,body) = grader.create_email(summary)
        print(body)
        return

    ep = endpoint(args)
    print(f"Requesting {ep} to grade {lab} timeout {args.timeout}...")
    cp = get_config()
    r = requests.post(ep, json={'action':'grade',
                                'auth':{STUDENT_EMAIL:cp[STUDENT][STUDENT_EMAIL],
                                        COURSE_KEY:cp[STUDENT][COURSE_KEY]},
                                'lab': lab},
        timeout = args.timeout )
    result = r.json()
    if not r.ok:
        print("Error: ",r.text)
        sys.exit(1)
    try:
        print_summary(result['summary'], verbose=getattr(args, "verbose", False))
    except KeyError:
        print(f"Invalid response from server:\n{json.dumps(result,indent=4)}")
        sys.exit(1)
    if args.debug:
        print(json.dumps(r.json(),indent=4))
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

def do_report_tests(_):
    """Generate markdown report of all available tests across all labs."""
    print("# E11 Lab Tests Report\n")
    print("This document lists all available tests for each lab.\n")

    for lab_num in range(LAB_MAX + 1):
        lab = f"lab{lab_num}"
        try:
            mod_name = f"e11.lab_tests.{lab}_test"
            mod = importlib.import_module(mod_name)
        except ModuleNotFoundError:
            continue

        # Collect tests from the module
        tests = collect_tests_in_definition_order(mod)

        # Also include imported_tests if present
        imported = getattr(mod, 'imported_tests', [])

        print(f"## {lab.upper()}\n")

        if not tests and not imported:
            print("*No tests defined.*\n")
            continue

        # List all test functions (including imported ones)
        all_tests = {}  # name -> (function, is_imported)

        # Add imported tests
        for test_func in imported:
            func_name = getattr(test_func, '__name__', str(test_func))
            all_tests[func_name] = (test_func, True)

        # Add locally defined tests
        for name, test_func in tests:
            if name not in all_tests:
                all_tests[name] = (test_func, False)

        # Sort test names for consistent output
        test_names = sorted(all_tests.keys())

        # Print test list
        for test_name in test_names:
            test_func, _ = all_tests[test_name]

            docstring = ""
            if test_func and inspect.isfunction(test_func):
                docstring = inspect.getdoc(test_func) or ""
                # Clean up docstring - take first line only for brevity
                if docstring:
                    docstring = docstring.split('\n',maxsplit=1)[0].strip()

            if docstring:
                print(f"- **{test_name}**: {docstring}")
            else:
                print(f"- **{test_name}**")

        print()  # Blank line between labs

# pylint: disable=too-many-statements
def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--debug", help='Run in debug mode', action='store_true')
    parser.add_argument("--stage", help='Use stage API', action='store_true')
    parser.add_argument('--force', help='Run even if not on ec2',action='store_true')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # e11 config
    config_parser = subparsers.add_parser('config', help='Config E11 student variables')
    config_parser.add_argument("--get",action='store_true',help='get a value')
    config_parser.add_argument("--section", help='the section to --get or --setvalue')
    config_parser.add_argument("--key", help='the key to --get or --setvalue')
    config_parser.add_argument("--setvalue",help='set this value')
    config_parser.add_argument("--smash",action='store_true',help='if key is email, smash the results')
    config_parser.set_defaults(func=do_config)

    # e11 access [on|off|check]
    access_parser = subparsers.add_parser('access', help='Enable or disable access')
    access_parser.set_defaults(func=lambda _: access_parser.print_help())
    access_subparsers = access_parser.add_subparsers(dest='action')

    access_subparsers.add_parser('on', help='Enable SSH access').set_defaults(func=do_access_on)
    access_subparsers.add_parser('off', help='Disable SSH access').set_defaults(func=do_access_off)
    access_subparsers.add_parser('check', help='Report SSH access').set_defaults(func=do_access_check)
    access_subparsers.add_parser('check-dashboard',
                                 help='Report SSH access from the dashboard for authenticated users').set_defaults(func=do_access_check_dashboard)
    access_subparsers.add_parser('check-me', help='Report SSH access from the dashboard for anybody').set_defaults(func=do_access_check_me)

    # Other primary commands
    register_parser = subparsers.add_parser('register', help='Register this instance')
    register_parser.set_defaults(func=do_register)
    register_parser.add_argument('--quiet', help='Run quietly', action='store_true')
    register_parser.add_argument('--fixip', help='Fix the IP address', action='store_true')

    subparsers.add_parser('status', help='Report status of the e11 system.').set_defaults(func=do_status)
    subparsers.add_parser('update', help='Update the e11 system').set_defaults(func=do_update)
    subparsers.add_parser('version', help='Update the e11 system').set_defaults(func=do_version)
    subparsers.add_parser('doctor', help='Self-test the system').set_defaults(func=run_doctor)

    # e11 report [tests]
    report_parser = subparsers.add_parser('report', help='Generate reports')
    report_parser.set_defaults(func=lambda _: report_parser.print_help())
    report_subparsers = report_parser.add_subparsers(dest='report_type')
    report_subparsers.add_parser('tests', help='List all available tests in markdown format').set_defaults(func=do_report_tests)

    # e11 answer [lab] - answer solutions
    answer_parser = subparsers.add_parser('answer', help='Answer additional questions for a particular lab prior to grading')
    answer_parser.add_argument(dest='lab', help='Lab for answers')
    answer_parser.set_defaults(func=do_answer)

    # e11 grade [lab]
    grade_parser = subparsers.add_parser('grade', help='Request lab grading (run from course server)')
    grade_parser.add_argument(dest='lab', help='Lab to grade')
    grade_parser.add_argument('--verbose', help='print all details',action='store_true')
    grade_parser.add_argument('--direct', help='Instead of grading [student]public_ip from server, grade from this system. Requires SSH access to target')
    grade_parser.add_argument('-i','--identity','--pkey_pem', help='Specify public key to use for direct grading')
    grade_parser.add_argument("--timeout", type=int, default=GRADING_TIMEOUT+5)
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
        elif args.command=='report':
            pass  # report commands don't need EC2
        elif staff.enabled():
            pass
        elif args.force:
            print("WARNING: This should be run on EC2")
        else:
            print("ERROR: This must be run on EC2")
            sys.exit(1)
    args.func(args)
