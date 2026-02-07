
"""
e11 staff commands.
"""

import sys
import os
import time
from decimal import Decimal

from tabulate import tabulate
import boto3
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


from e11.e11core.e11ssh import E11Ssh
from e11.e11_common import (dynamodb_client,dynamodb_resource,A,create_new_user,users_table,get_user_from_email,queryscan_table,generate_direct_login_url,EmailNotRegistered)

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
    print("Lab instructions are at https://github.com/Harvard-CSCI-E-11/spring26")
    try:
        user = get_user_from_email(args.email)
        if user.course_key is None:
            print(f"Internal Error: User {args.email} exists but has no course key? user={user}")
            sys.exit(1)
        login_url = generate_direct_login_url(user.user_id, user.course_key)
        print(f"User {args.email} already exists.\ncourse_key={user.course_key}\nLogin URL: {login_url}")
        sys.exit(0)
    except EmailNotRegistered:
        pass
    user = create_new_user(args.email)
    if user.course_key is None:
        print(f"User {args.email} created but course_key is None?")
        sys.exit(1)
    login_url = generate_direct_login_url(user.user_id, user.course_key)
    print(f"Registered {args.email}\ncourse_key={user.course_key}\nLogin URL: {login_url}")

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
    kwargs = { 'FilterExpression':Attr(A.SK).eq(A.SK_USER),
               'ProjectionExpression': 'user_registered, email, preferred_name, claims'}

    try:
        response = table.scan( **kwargs )
    except ClientError:
        print("No access: ",table)
        sys.exit(1)
    items = response['Items']
    while 'LastEvaluatedKey' in response:
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = table.scan( **kwargs)
        items.extend(response['Items'])

    pitems = []
    for item in items:
        try:
            raw = item.get('user_registered',0)
            if isinstance(raw, (str,int,Decimal)):
                user_registered = int(raw)
            else:
                user_registered = 0
        except TypeError:
            user_registered = 0
        pitems.append({"Registered":time.asctime(time.localtime(user_registered)),
                       "Email":item.get('email',""),
                       "Name":item.get('preferred_name',""),
                       'HarvardKey':("YES" if item.get('claims') else "NO")})

    def sortkey(a):
        return a.get('Name','') + "~" + a.get('Email','')
    print(tabulate( sorted(pitems,key=sortkey), headers='keys'))

def get_class_list():
    """Get the entire class list. Requires a scan."""
    kwargs:dict = {'FilterExpression':Key(A.SK).eq(A.SK_USER),
                   'ProjectionExpression': f'{A.USER_ID}, email, preferred_name' }
    return queryscan_table(users_table.scan, kwargs)

def do_student_grades_lab(args):
    """Grades for a lab. Requires a scan."""
    lab = args.whowhat
    userid_to_user = {cl['user_id']:cl for cl in get_class_list()}
    kwargs:dict = {
        'FilterExpression' : ( Key(A.SK).begins_with(f'{A.SK_GRADE_PREFIX}{lab}#') ),
        'ProjectionExpression' : f'{A.USER_ID}, {A.SK}, {A.SCORE}',
    }
    items = queryscan_table(users_table.scan, kwargs)
    print("Grades for lab:",lab)

    all_grades = [(userid_to_user[r[A.USER_ID]]['email'],Decimal(r[A.SCORE]),r[A.SK].split('#')[2]) for r in items if r[A.SK].count('#')==2]
    all_grades.sort()
    if args.all:
        print(tabulate(all_grades))
        return

    # Need to remove the grades that are not the highest. Do one pass to find the higest grade by processing the list in reverse
    highest_grade = {}
    for r in reversed(all_grades):
        if r[0] not in highest_grade:
            highest_grade[r[0]] = r
    # Now print
    print(tabulate(sorted(highest_grade.values())))

def do_student_grades_email(args):
    email = args.whowhat
    print("Grades for: ",email)
    user = get_user_from_email(email)
    for (k,v) in sorted(dict(user).items()):
        print(f"{k}:{v}")

    kwargs:dict = {'KeyConditionExpression' : (
        Key(A.USER_ID).eq(user.user_id) &
        Key(A.SK).begins_with(A.SK_GRADE_PREFIX)
    )}
    items = queryscan_table(users_table.query, kwargs)
    print("*** note - only print the highest grade")
    for item in items:
        print(item)


def do_student_grades(args):
    if args.whowhat.startswith("lab"):
        do_student_grades_lab(args)
    else:
        do_student_grades_email(args)
