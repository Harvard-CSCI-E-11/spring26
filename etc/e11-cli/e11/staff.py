
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


from .e11core.e11ssh import E11Ssh
from .e11_common import (dynamodb_client,dynamodb_resource,A,create_new_user,users_table,get_user_from_email,queryscan_table,generate_direct_login_url,EmailNotRegistered)

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

def do_student_grades_lab(lab, highest_grade=False):
    """
    Display grade information for all students who submitted a specific lab.

    Args:
        lab (str): Lab identifier (e.g., 'lab1', 'lab2', 'lab3', etc.)
        highest_grade (bool): Output mode selector
            - False (default): Show all submission attempts followed by highest grades
            - True: Show only highest grades (activated by --highest-grade flag)

    Output Format:
        CSV format with header: email,name,score,timestamp
        Names are quoted to handle spaces and special characters safely

    Sorting:
        - When highest_grade=False: Sorted by email address (alphabetically)
        - When highest_grade=True: Sorted by preferred_name (case-insensitive)
          with 'N/A' and 'None' values sorted to the end

    Data Source:
        - Queries DynamoDB e11-users table for grade records matching grade#labN#timestamp pattern
        - Retrieves student information (email, preferred_name) via get_class_list()
        - For students with multiple submissions, tracks and displays the highest score

    Returns:
        None. Prints results directly to stdout.

    Example Output (highest_grade=True):
        Grades for lab: lab1
        email,name,score,timestamp
        dmalfoy@hogwarts.edu,"Draco Malfoy",4.17,grade#lab1#2026-01-30T16:45:18.345678
        hpotter@hogwarts.edu,"Harry Potter",5.0,grade#lab1#2026-01-29T14:30:22.123456
        hgranger@hogwarts.edu,"Hermione Granger",5.0,grade#lab1#2026-01-28T09:15:33.789012
    """
    # Build user_id to user info mapping (email, preferred_name)
    userid_to_user = {cl['user_id']:cl for cl in get_class_list()}

    # Query DynamoDB for all grade records matching this lab (e.g., grade#lab1#timestamp)
    kwargs:dict = {
        'FilterExpression' : ( Key(A.SK).begins_with(f'{A.SK_GRADE_PREFIX}{lab}#') ),
        'ProjectionExpression' : f'{A.USER_ID}, {A.SK}, {A.SCORE}',
    }
    items = queryscan_table(users_table.scan, kwargs)
    print("Grades for lab:",lab)

    # Process all submissions and track highest grade per student
    # grades dict structure: {email: (preferred_name, score, timestamp)}
    grades = {}
    for item in items:
        # Extract student information for this grade record
        email = userid_to_user[item['user_id']]['email']
        preferred_name = userid_to_user[item['user_id']].get('preferred_name', 'N/A')
        score = Decimal(item[A.SCORE])
        row = [preferred_name, email, item[A.SCORE], item[A.SK]]

        # Print all attempts unless --highest-grade flag is set
        if not highest_grade:
            print(row)

        # Update highest grade if this is first submission or higher score
        if (email not in grades) or (grades[email][1] < score):
            grades[email] = (preferred_name, score, item[A.SK])

    # Sort by preferred_name (case-insensitive) if --highest-grade, otherwise by email
    if highest_grade:
        sorted_grades = sorted(grades.items(), key=lambda x: (x[1][0] in ['N/A', 'None'], x[1][0].upper()))
    else:
        sorted_grades = sorted(grades.items())

    # Print header and highest grade for each student
    print("email,name,score,timestamp")
    for (k,v) in sorted_grades:

        # Protect CSV file from  commas in names
        print(f'{k},"{v[0]}",{v[1]},{v[2]}')

def do_student_grades_email(email):
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
    whowhat = args.whowhat
    if whowhat.startswith("lab"):
        do_student_grades_lab(whowhat, highest_grade=args.highest_grade)
    else:
        do_student_grades_email(whowhat)


def add_staff_parsers(parser,subparsers):
    ca = subparsers.add_parser('check-access', help='E11_STAFF: Check to see if we can access a host')
    ca.add_argument(dest='host', help='Host to check')
    ca.set_defaults(func=do_check_access)

    ca = subparsers.add_parser('register-email', help='E11_STAFF: Register an email address directly with DynamoDB')
    ca.add_argument(dest='email', help='Email address to register')
    ca.set_defaults(func=do_register_email)

    ca = subparsers.add_parser('student-report', help='E11_STAFF: Generate a report directly from DynamoDB')
    ca.set_defaults(func=do_student_report)
    ca.add_argument("--dump",help="Dump all information", action='store_true')

    ca = subparsers.add_parser('grades', help='E11_STAFF: Show grades or a student or a lab')
    ca.add_argument(dest='whowhat', help='Email address or a lab')
    ca.add_argument('--highest-grade', action='store_true',
                    help='Show only highest grades, sorted by name')
    ca.set_defaults(func=do_student_grades)

    parser.add_argument("--keyfile",help="SSH private key file")
