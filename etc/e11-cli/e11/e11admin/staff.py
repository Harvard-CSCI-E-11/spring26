
"""
e11 staff commands.
"""

import sys
import os
import time
import csv
from decimal import Decimal

from tabulate import tabulate
import boto3
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError


from e11.e11core.e11ssh import E11Ssh
from e11.e11_common import (dynamodb_client,dynamodb_resource,A,create_new_user,users_table,
                            get_user_from_email,queryscan_table,generate_direct_login_url,EmailNotRegistered)

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

################################################################
###
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
        print(item)
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
                       "Preferred Name":item.get('preferred_name',""),
                       "Claims Name":item.get('claims',{}).get('name'),
                       'HarvardKey':("YES" if item.get('claims') else "NO")})

    def sortkey(a):
        return a.get('Name','') + "~" + a.get('Email','')
    print(tabulate( sorted(pitems,key=sortkey), headers='keys'))

def get_class_list():
    """Get the entire class list. Requires a scan."""
    kwargs:dict = {'FilterExpression':Key(A.SK).eq(A.SK_USER),
                   'ProjectionExpression': f'{A.USER_ID}, email, preferred_name, claims' }
    return queryscan_table(users_table.scan, kwargs)

################################################################
## Print and upload student grades

def print_grades(items, args):
    userid_to_user = {cl['user_id']:cl for cl in get_class_list()}
    all_grades = [(userid_to_user[r[A.USER_ID]]['email'],Decimal(r[A.SCORE]),r[A.SK].split('#')[2])
                  for r in items if r[A.SK].count('#')==2]
    if not args.all:
        # Remove all but the highest grades
        highest_grade = {}
        for row in all_grades:
            (email,grade,_sk) = row
            if (email not in highest_grade) or (grade>highest_grade[email][1]):
                highest_grade[email] = row
        all_grades = list(highest_grade.values())

    all_grades.sort()
    # Now print
    print(tabulate(sorted(highest_grade.values())))

def get_items(whowhat):
    """Return either the grades for a lab or a person"""
    if whowhat.startswith("lab"):
        kwargs:dict = {
            'FilterExpression' : ( Key(A.SK).begins_with(f'{A.SK_GRADE_PREFIX}{whowhat}#') ),
            'ProjectionExpression' : f'{A.USER_ID}, {A.SK}, {A.SCORE}',
        }
        return queryscan_table(users_table.scan, kwargs)
    user = get_user_from_email(whowhat)
    for (k,v) in sorted(dict(user).items()):
        print(f"{k}:{v}")

    kwargs:dict = {'KeyConditionExpression' : (
        Key(A.USER_ID).eq(user.user_id) &
        Key(A.SK).begins_with(A.SK_GRADE_PREFIX)
    )}
    return queryscan_table(users_table.query, kwargs)

def do_student_grades(args):
    items = get_items(args.whowhat)
    print_grades(items, args)

def canvas_grades(args):
    """Get all of the grades and merge them with an exported grade sheet. This requires name matching

Required columns and order

0: Student Name
1: Student ID
2: SIS User ID (only required if you use SIS)
3: SIS Login ID (only required if you use SIS)
4: Section
5: Assignment (this can be for an existing assignment or a new assignment; retain IDs for existing assignments)
"""

    if not args.lab.startswith("lab"):
        print(f"'{args.lab}' is not in the correct format for a lab (e.g. lab1, lab2, lab3...)")
        sys.exit(1)

    if not args.template.exists():
        print(f"{args.template} does not exist.")
        sys.exit(1)

    template_names = []
    output_headers = []
    with open(args.template, 'r') as f:
        reader = csv.reader(f)
        headers = next(reader)
        points_possible = next(reader)
        assert points_possible[0].strip().startswith("Points Possible") # bogus line
        output_headers.extend(headers[0:5])

        # Find the assignment column
        labcol = None
        for (col,text) in enumerate(headers):
            if args.lab in text.lower().replace(' ','').replace('#','') and "quiz" not in text.lower():
                print(f"Found {args.lab} in column {col}: '{text}'")
                labcol = col
                output_headers.append(text)
                break
        if labcol is None:
            print(f"Could not find {args.lab} in columns:")
            for (col,text) in enumerate(headers):
                print(f"{col}: {text}")
            sys.exit(1)

        # Now get all of the names
        for name in reader:
            if name[0]=='Student, Test':
                continue
            template_names.append(name)
        print(f"Read {len(template_names)} names from template")

    if args.outfile.exists():
        print(f"{args.outfile} exists. Delete it first")
        sys.exit(1)

    output_names_and_grades = []
    output_names_and_grades.append(output_headers)

    # Find all of the exact matches.
    # First verify that nobody has the same name
    seen_names = set()
    dups = 0
    for name in template_names:
        cname = name[0].lower()
        if cname in seen_names:
            print("Duplicate student name:",cname)
            dups += 1
        seen_names.add(cname)
    if dups>0:
        print("Cannot continue. Two students with the same name.")
        sys.exit(1)

    # Get the class list as a set by userid
    class_list = {item[A.USER_ID]:item for item in get_class_list() if item.get('claims')}
    if len(class_list)==0:
        print("no grades found")
        sys.exit(1)

    # Get the grades as a set by userid and add each grade to the user_id in the class list
    for item in get_items(args.lab):
        try:
            class_list[item[A.USER_ID]][A.SCORE] = item[A.SCORE]
        except KeyError:
            print("cannot match grades:",item)
            pass

    def exact_match(name):
        (last,first) = name.lower().split(", ")
        lower_name = first + " " + last
        for item in class_list.values():
            claims_name = item['claims']['name'].lower()
            if lower_name == claims_name:
                return item
        return None

    # Create the exact matches
    unmatched_names = []
    for name in template_names:
        em = exact_match(name[0])
        if em:
            try:
                grade = em[A.SCORE]
                output_names_and_grades.append( name[0:5] + [grade])
            except KeyError:
                print("No grade for",name)
            del class_list[em[A.USER_ID]]
        else:
            unmatched_names.append(name)

    # debug
    print("matched:")
    for row in output_names_and_grades:
        print(row)
    print("Total grades:",len(output_names_and_grades)-1,"\n")
    print("unmatched grades:")
    unmatched = []
    for item in class_list:
        if A.SCORE in item:
            print(item)
            unmatched.append(item)
    if unmatched > 0:
        print("Unmatched.  Will not continued")
        sys.exit(1)

    print("Generating output")
    with args.outfile.open("w") as f:
        writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in output_names_and_grades:
            writer.writerow(row)











################################################################
## Force grading of a specific student

def find_queue():
    # Find the grade queue
    sqs = boto3.client('sqs')
    r = sqs.list_queues()
    for q in r['QueueUrls']:
        if 'prod-home-queue' in q:
            return q
    raise RuntimeError("prod-home-queue SQS queue not found")

def force_grades(args):
    queue_name = find_queue()
    print("sending message to",queue_name)
    os.environ['SQS_QUEUE_URL'] = queue_name
    if 'SQS_SECRET_ID' not in os.environ:
        raise RuntimeError("Set environment variable SQS_SECRET_ID")

    base_dir = os.path.dirname(__file__)
    home_path = os.path.abspath(os.path.join(base_dir, "..", "..", "lambda-home", "src"))
    if home_path not in sys.path:
        sys.path.append(home_path)
    from home_app import home # pylint: disable=import-error, disable=import-outside-toplevel

    home.queue_grade(args.email,args.lab) # is it this simple?
