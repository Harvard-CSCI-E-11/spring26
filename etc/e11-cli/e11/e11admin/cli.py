"""
e11admin main program
"""

import time
import argparse
import sys
import json
from typing import Any, Dict, List
from pathlib import Path

import boto3
from boto3.dynamodb.conditions import Key,Attr
from tabulate import tabulate
from e11.e11_common import A,make_course_key,get_user_from_email

from . import staff

dynamodb_client = boto3.client('dynamodb')
dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('e11-users')

HELP_TEXT = """e11admin - Quick reference

List information about a student by email:
  e11admin student-report --email <email>
  e11admin grades <email>

Force a grade for a specific lab:
  e11admin force-grade <email> <lab>
  Example: SQS_SECRET_ID=<secret-arn> AWS_PROFILE=fas AWS_REGION=us-east-1 \\
    e11admin force-grade student@example.com lab1

Access a student's VM via SSH:
  e11admin ssh <email>

Run 'e11admin --help' for full option list."""

def validate_dynamodb():
    missing = 0
    correct = 0
    r = dynamodb_client.list_tables()
    print("DynamoDB Tables:")
    for table_name in r['TableNames']:
        print(f"- {table_name}")
        correct += 1
    for name in ['Leaderboard','e11-users','home-app-prod-sessions','home-app-stage-sessions']:
        if name not in r['TableNames']:
            print(f"missing table: {name}")
            missing += 1
    print("")
    if missing>0:
        print("Wrong AWS_PROFILE?")
        sys.exit(1)

def get_all(*, sk=None, user_id=None, projection=None) -> List[Dict[str, Any]]:
    """Search the users table and returns all of the recoreds with a particular sk.
    Currently this requires a scan. We need to modify the schema to allow us to do this efficiently with a query.
    """
    # Use a FilterExpression to find items where 'sk' equals 'USER'
    # Start the scan

    kwargs = {}
    if sk is not None:
        kwargs['FilterExpression'] = Attr('sk').eq(sk)
    if projection is not None:
        kwargs['ProjectionExpression'] = projection

    func = users_table.scan
    if user_id is not None:
        func = users_table.query
        kwargs['KeyConditionExpression'] = Key('user_id').eq(user_id)

    response = func( **kwargs )
    items = response['Items']
    calls = 1
    while 'LastEvaluatedKey' in response:
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = func( **kwargs )
        items.extend(response['Items'])
        calls += 1

    print(f"Scan complete. Found {len(items)} users. calls={calls}")
    return items

def get_name(user):
    if preferred_name := user.get('preferred_name'):
        return preferred_name
    if claims := user.get('claims'):
        return claims.get('name','n/a')
    return 'n/a'

def show_registered_users(claims):
    users = get_all(sk='#',projection='user_id,user_registered,email,public_ip,claims,preferred_name')
    pusers = [ (get_name(user),
                user.get('email','n/a'),
                'Y' if user.get('claims') else '',
                time.asctime(time.localtime(int(user.get('user_registered',0)))),
                user.get('public_ip','n/a'),
                user.get('user_id')
                )
              for user in users]
    if claims:
        pusers = [user for user in pusers if user[2]]
    pusers.sort()
    print(f"\n\nUsers: {len(pusers)}")
    print(tabulate(pusers,headers=['preferred_name','email','Harvard','registered','public_ip','user_id']))
    print("")

def dump_users_table(args,user_id=None):
    print("================ dump_users_table ================")

    items = get_all(user_id=user_id)
    print(f"Scan complete. Found {len(items)} items")
    printable = {}
    sk_prev = ''
    for item in items:
        user_id = item['user_id']
        if user_id not in printable:
            if args.dump:
                print("")
            printable[user_id] = user_id[0:3] + " " + get_name(item)
        sk0 = item['sk'].split('#')[0]
        if sk0=='':
            print(printable[user_id],item['sk'],item.get('message','')[0:40])
        if args.dump:
            if sk0 != sk_prev:
                print("---")
            print(item)
        sk_prev = sk0
    return items

def delete_items(items):
    # 2. Use batch_writer for efficient deletion
    # The batch_writer automatically handles buffering (up to 25 items) and unprocecessed items
    confirm = input(f"Really delete {len(items)} items? ")
    if confirm[0]=='Y':
        with users_table.batch_writer() as batch:
            for item in items:
                batch.delete_item(Key={'user_id':item['user_id'], 'sk':item['sk']})
        print("deleted")

def delete_item(*,user_id,sk):
    users_table.delete_item(Key={'user_id':user_id, 'sk':sk})

def new_course_key(user_id):
    user = get_user_from_email(user_id)
    if not user:
        print("User not found")
        return
    print("user:",json.dumps(dict(user),indent=4,default=str))
    newkey = make_course_key()
    print("new key:", newkey)
    users_table.update_item(
        Key={A.USER_ID:user.user_id, A.SK: A.SK_USER},
        UpdateExpression=f'SET {A.COURSE_KEY} = :new_course_key',
        ExpressionAttributeValues={ ':new_course_key': newkey}
    )
    user = get_user_from_email(user_id)
    print("new user:",json.dumps(dict(user),indent=4,default=str))


def do_class(args):
    validate_dynamodb()

    if args.delete_item:
        delete_item(user_id=args.user_id, sk=args.sk)

    if args.newkey:
        new_course_key(args.newkey)
        return

    show_registered_users(claims=args.claims)
    if args.dump:
        dump_users_table(args)

    if args.delete_userid:
        items = dump_users_table(args,user_id=args.delete_userid)
        if not items:
            print("user not found")
            sys.exit(0)
        response = input("really delete user? [n/YES]")
        if response=='YES':
            delete_items(items)

def do_help(_args):
    print(HELP_TEXT)

# pylint: disable=too-many-statements
def main():
    parser = argparse.ArgumentParser(prog='e11admin', description='E11 admin program',
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', required=True)
    class_parser = subparsers.add_parser('class', help='Commands for E11 class')
    class_parser.set_defaults(func=do_class)
    class_parser.add_argument("--dump", help='Dump all ', action='store_true')
    class_parser.add_argument("--delete_userid", help='Delete a user')
    class_parser.add_argument("--delete_item", help='Delete a user_id, sk',action='store_true')
    class_parser.add_argument("--newkey", help="Create a new course key for the user specified by email address")
    class_parser.add_argument("--user_id", help='Specify the user_id')
    class_parser.add_argument("--sk", help='Specify the sk')
    class_parser.add_argument("--claims", help="Only show users with claims", action='store_true')

    ca = subparsers.add_parser('check-access', help='Check to see if we can access a host')
    ca.add_argument(dest='host', help='Host to check')
    ca.add_argument("--keyfile",help="SSH private key file")
    ca.set_defaults(func=staff.do_check_access)

    ca = subparsers.add_parser('register-email', help='Register an email address directly with DynamoDB')
    ca.add_argument(dest='email', help='Email address to register')
    ca.set_defaults(func=staff.do_register_email)

    ca = subparsers.add_parser('edit-email', help='Edit a user property by email')
    ca.add_argument(dest='email', help='Email address to edit')
    ca.add_argument("--alt", help="alternative email")
    ca.add_argument("--remove", help="remove alternative email",action='store_true')
    ca.set_defaults(func=staff.do_edit_email)

    ca = subparsers.add_parser('student-report', help='Generate a report directly from DynamoDB')
    ca.set_defaults(func=staff.do_student_report)
    ca.add_argument('--email', help='Just this email')
    ca.add_argument("--dump",help="Dump all information", action='store_true')

    ca = subparsers.add_parser('grades', help='Show grades or a student or a lab')
    ca.add_argument(dest='whowhat', help='Email address or a lab')
    ca.add_argument("--all",help="Show all grades (otherwise just show highest)", action="store_true")
    ca.add_argument("--claims",help="only students that have claims", action="store_true")
    ca.set_defaults(func=staff.do_student_grades)

    ca = subparsers.add_parser('force-grade', help='Force the grading of a student or lab')
    ca.add_argument(dest='email', help='email to grade (use "all" for all)')
    ca.add_argument(dest='lab', help='lab to grade')
    ca.add_argument(dest='who', help='Who manually forced the grade')
    ca.add_argument("--stage", action="store_true", help="use stage.csci-e-11.org")
    ca.set_defaults(func=staff.force_grades)

    ca = subparsers.add_parser('canvas-grades', help='Create grade sheet for upload to Canvas')
    ca.add_argument(dest='lab', help='lab to grade')
    ca.add_argument("--template", help="Canvas exported grade sheet", type=Path, required=True)
    ca.add_argument("--outfile", help="Output file to create", type=Path, required=True)
    ca.set_defaults(func=staff.canvas_grades)

    ca = subparsers.add_parser('ssh', help="access a student's VM via SSH (specify email address)")
    ca.add_argument(dest='email', help='email address')
    ca.set_defaults(func=staff.ssh_access)

    ca = subparsers.add_parser('help', help='Show quick reference for common tasks')
    ca.set_defaults(func=do_help)

    args = parser.parse_args()
    args.func(args)
    return 0

if __name__=="__main__":
    sys.exit(main())
