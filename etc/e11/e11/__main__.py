#!/usr/bin/env python3.11
"""
The CSCI E-11 e11 program.
"""
import argparse
import sys
import logging
import os
import shutil
import configparser
from os.path import join,abspath,dirname

logging.basicConfig(format='%(asctime)s  %(filename)s:%(lineno)d %(levelname)s: %(message)s', force=True)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HOME_DIR = os.getenv("HOME")
AUTHORIZED_KEYS_FILE = join( HOME_DIR , ".ssh", "authorized_keys")
CSCIE_BOT_KEYFILE = join( dirname(abspath(__file__)), 'csci-e-11-bot.pub')
CONFIG_FILE = join( HOME_DIR, 'e11-config.ini')
# Student properties
STUDENT='student'
STUDENT_EMAIL='email'
STUDENT_NAME='name'
STUDENT_HUID='huid'
INSTANCE_IPADDR='ipaddr'
STUDENT_ATTRIBS = [STUDENT_NAME,STUDENT_EMAIL,STUDENT_HUID,INSTANCE_IPADDR]

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
    logger.info("Checking access status...")
    key = cscie11_bot_key()
    with open(AUTHORIZED_KEYS_FILE,'r') as f:
        for line in f:
            if line == key:
                logger.info("CSCI E-11 Course Admin HAS ACCESS to this instance.")
                return
    logger.info("CSCI E-11 Course Admin DOES NOT HAVE ACCESS to this instance.")


def do_config(args):
    cp = configparser.ConfigParser()
    try:
        with open(CONFIG_FILE,'r') as f:
            cp.read_file(f)
    except FileNotFoundError:
        pass
    if STUDENT not in cp:
        cp.add_section(STUDENT)
    for attrib in STUDENT_ATTRIBS:
        while True:
            buf = input(f"{attrib}: [{cp[STUDENT].get(attrib,'')}] ")
            if buf:
                cp[STUDENT][attrib] = buf
            if cp[STUDENT].get(attrib,'') != '':
                break
    with open(CONFIG_FILE,'w') as f:
        cp.write(f)


def main():
    parser = argparse.ArgumentParser(prog='e11', description='Manage student VM access')
    subparsers = parser.add_subparsers(dest='command', required=True)

    # e11 access [on|off|check]
    access_parser = subparsers.add_parser('access', help='Enable or disable access')
    access_subparsers = access_parser.add_subparsers(dest='action', required=True)

    access_subparsers.add_parser('on', help='Enable SSH access').set_defaults(func=do_access_on)
    access_subparsers.add_parser('off', help='Disable SSH access').set_defaults(func=do_access_off)
    access_subparsers.add_parser('check', help='Report SSH access').set_defaults(func=do_access_check)

    # e11 config
    subparsers.add_parser('config', help='Config E11 student variables').set_defaults(func=do_config)


    # e11 status check
    #status_parser = subparsers.add_parser('status', help='Check access status')

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
