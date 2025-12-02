
"""
e11 staff commands.
"""

import sys
import os
import time

from tabulate import tabulate
import boto3
from boto3.dynamodb.conditions import Attr

from .e11core.e11ssh import E11Ssh
from .e11_common import dynamodb_client,dynamodb_resource,A,create_new_user

def enabled():
    return os.getenv('E11_STAFF','0')[0:1].upper() in ['Y','T','1']

def do_check_access(args):
    print(f"Checking access to {args.host} from this host (not the lambda server)")
    with E11Ssh(args.host, key_filename=args.keyfile) as ssh:
        rc, out, err = ssh.exec("hostname")
        if rc!=0:
            print("rc=",rc)
        if out:
            print("out:\n",out)
        if err:
            print("err:\n",err)

def do_register_email(args):
    email = args.email
    # See if the email exists
    response = dynamodb_resource.Table('e11-users').scan(FilterExpression = Attr('email').eq(email))
    if response.get('Items'):
        user = response.get('Items')[0]
        print(f"User {email} already exists.\ncourse_key={user[A.COURSE_KEY]}")
        sys.exit(0)
    user = create_new_user(email)
    print(f"Registered {email}\ncourse_key={user[A.COURSE_KEY]}")

def do_student_report(args):
    session = boto3.session.Session()
    current_profile = session.profile_name
    print(f"Current AWS Profile: {current_profile}\n")

    response = dynamodb_client.list_tables()
    print("DynamoDB Tables:")
    for table_name in response['TableNames']:
        table_description = dynamodb_client.describe_table(TableName=table_name)
        item_count = table_description['Table'].get('ItemCount',0)
        print(f"Table: {table_name}, Approximate Item Count: {item_count}")

        # dump the whole table?
        if args.dump:
            kwargs = {}
            while True:
                response = dynamodb_resource.Table( table_name ).scan(**kwargs)
                for item in response.get('Items'):
                    print(item)
                lek = response.get('LastEvaluatedKey')
                if not lek:
                    break
                kwargs['ExclusiveStartKey'] = lek
            print("-------------------------")

    print("Users:")
    table = dynamodb_resource.Table('e11-users')
    kwargs = { 'FilterExpression':Attr('sk').eq('#'),
               'ProjectionExpression': 'user_registered, email, preferred_name, claims'}

    response = table.scan( **kwargs )
    items = response['Items']

    while 'LastEvaluatedKey' in response:
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = table.scan( **kwargs)
        items.extend(response['Items'])

    pitems = []
    for item in items:
        raw_user_registered = item.get('user_registered',0)
        if isinstance(raw_user_registered, (int,str)):
            user_registered = int(raw_user_registered)
        else:
            user_registered = 0
        pitems += {"Registered":time.asctime(time.localtime(user_registered)),
                   "Email":item.get('email'),
                   "Name":item.get('preferred_name'),
                   'HarvardKey':("YES" if item.get('claims') else "NO")}

    print(tabulate(pitems,headers='keys'))



def add_parsers(parser,subparsers):
    ca = subparsers.add_parser('check-access', help='E11_STAFF: Check to see if we can access a host')
    ca.add_argument(dest='host', help='Host to check')
    ca.set_defaults(func=do_check_access)

    ca = subparsers.add_parser('register-email', help='E11_STAFF: Register an email address directly with DynamoDB')
    ca.add_argument(dest='email', help='Email address to register')
    ca.set_defaults(func=do_register_email)

    ca = subparsers.add_parser('student-report', help='E11_STAFF: Generate a report directly from DynamoDB')
    ca.set_defaults(func=do_student_report)
    ca.add_argument("--dump",help="Dump all information", action='store_true')

    parser.add_argument("--keyfile",help="SSH private key file")
