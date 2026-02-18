
"""
e11 staff commands.
"""

import sys
import os
import time
import csv
import subprocess
import signal
import functools
from typing import Any, Dict, List
from decimal import Decimal

from tabulate import tabulate
import boto3
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from e11.e11core.e11ssh import E11Ssh
from e11.e11core.utils import smash_email
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
def _dump_table_items(table_name, user_id):
    """Helper function to dump table items with optional user filtering."""
    kwargs = {}
    while True:
        response = dynamodb_resource.Table(table_name).scan(**kwargs)
        for item in response.get('Items'):
            if user_id is None or item.get('user_id', 'n/a') == user_id:
                print(item)
        lek = response.get('LastEvaluatedKey')
        if not lek:
            break
        kwargs['ExclusiveStartKey'] = lek
    print("-------------------------")

def _get_user_registered_time(item):
    """Extract and normalize user registered timestamp."""
    try:
        raw = item.get('user_registered', 0)
        if isinstance(raw, (str, int, Decimal)):
            return int(raw)
        return 0
    except TypeError:
        return 0

def _format_user_item(item):
    """Format a user item for display."""
    user_registered = _get_user_registered_time(item)
    try:
        claims_name = item['claims']['name']
    except (TypeError, KeyError):
        claims_name = 'n/a'

    return {
        "Registered": time.asctime(time.localtime(user_registered)),
        "Email": item.get('email', ""),
        "Preferred Name": item.get('preferred_name', ""),
        "Claims Name": claims_name,
        'HarvardKey': ("YES" if item.get('claims') else "NO")
    }

def do_student_report(args):
    session = boto3.session.Session()
    current_profile = session.profile_name
    print(f"Current AWS Profile: {current_profile}\n")

    response = dynamodb_client.list_tables()
    user_id = get_user_from_email(args.email)['user_id'] if args.email else None

    print("DynamoDB Tables:")
    for table_name in response['TableNames']:
        table_description = dynamodb_client.describe_table(TableName=table_name)
        item_count = table_description['Table'].get('ItemCount', 0)
        print(f"Table: {table_name}, Approximate Item Count: {item_count}")

        if args.dump:
            _dump_table_items(table_name, user_id)

    print("Users:")
    table = dynamodb_resource.Table('e11-users')
    kwargs = {
        'FilterExpression': Attr(A.SK).eq(A.SK_USER),
        'ProjectionExpression': 'user_registered, email, preferred_name, claims'
    }

    try:
        response = table.scan(**kwargs)
    except ClientError:
        print("No access: ", table)
        sys.exit(1)

    items = response['Items']
    while 'LastEvaluatedKey' in response:
        kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
        response = table.scan(**kwargs)
        items.extend(response['Items'])

    if args.email:
        items = [item for item in items if item['email'] == args.email]

    pitems = []
    for item in items:
        print(item)
        pitems.append(_format_user_item(item))

    def sortkey(a):
        return a.get('Name', '') + "~" + a.get('Email', '')
    print(tabulate(sorted(pitems, key=sortkey), headers='keys'))

@functools.lru_cache(maxsize=2)
def get_class_list() -> List[Dict[str, Any]]:
    """Get the entire class list. Requires a scan."""
    kwargs:dict = {'FilterExpression':Key(A.SK).eq(A.SK_USER),
                   'ProjectionExpression': f'{A.USER_ID}, email, preferred_name, claims' }
    return queryscan_table(users_table.scan, kwargs)

@functools.lru_cache(maxsize=2)
def userid_to_user():
    """returns a dictionary of userid to user entries"""
    return {cl['user_id']:cl for cl in get_class_list()}

def userid_to_email(user_id):
    return userid_to_user()[user_id]['email']

################################################################
## Print and upload student grades

def print_grades(items, args):
    all_grades = [(userid_to_email(r[A.USER_ID]),
                   Decimal(r[A.SCORE]),
                   r[A.SK].split('#')[2],
                   r[A.USER_ID])
                  for r in items if r[A.SK].count('#')==2]
    if not args.all:
        # Remove all but the highest grades
        highest_grade = {}
        for row in all_grades:
            (email, grade, _sk, _user_id) = row
            if (email not in highest_grade) or (grade>highest_grade[email][1]):
                highest_grade[email] = row
        all_grades = list(highest_grade.values())

    if args.claims:
        # remove grades for which there are no claims
        all_grades = [row for row in all_grades if userid_to_user().get(row[3], {}).get('claims')]

    all_grades.sort()
    # Now print
    print(tabulate(all_grades))
    print("Total:",len(all_grades))

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

# pylint:  disable=too-many-branches,disable=too-many-statements
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
    if len(unmatched) > 0:
        print("Unmatched.  Will not continued")
        sys.exit(1)

    print("Generating output")
    with args.outfile.open("w") as f:
        writer = csv.writer(f, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        for row in output_names_and_grades:
            writer.writerow(row)



################################################################
## Force grading of a specific student

def find_queue(substr, stage=False):
    # Find the grade queue
    sqs = boto3.client('sqs')
    r = sqs.list_queues()
    for q in r['QueueUrls']:
        print("queue:",q)
        if stage and "stage" not in q:
            continue
        if substr in q:
            return q
    raise RuntimeError(f"SQS queue with substring {substr} not found")

def find_secret(substr):
    # Find the grade queue
    secrets_manager = boto3.client('secretsmanager')
    r = secrets_manager.list_secrets()
    for s in r['SecretList']:
        name = s.get('Name','')
        print("secret:",name)
        if substr in name:
            return name
    raise RuntimeError(f"Secret with substring {substr} not found")

def update_path():
    """update the path and return (home,api)."""
    base_dir = os.path.dirname(__file__)
    home_path = os.path.abspath(os.path.join(base_dir, "..", "..", "lambda-home", "src"))
    if home_path not in sys.path:
        sys.path.append(home_path)

    from home_app import home,api # type: ignore # pylint: disable=import-error, disable=import-outside-toplevel
    return (home,api)

def force_grades(args):
    (home,_) = update_path()
    queue_name  = find_queue('home-queue', stage=args.stage)
    secret_name = find_secret("sqs-auth-secret")
    print("sending message to",queue_name)
    print("using secret",secret_name)
    os.environ['SQS_QUEUE_URL'] = queue_name
    os.environ['SQS_SECRET_ID'] = secret_name
    message = f"Grading was manually queued by {args.who}"

    if args.email=='all':
        # Find all of the student in args.lab that did not get a 5
        high_grades = {}

        # start every student with a 0
        for item in get_class_list():
            high_grades[ userid_to_email(item['user_id']) ] = Decimal(0.0)

        items = get_items(args.lab)
        for i in items:
            email = userid_to_email(i['user_id'])
            score = Decimal(i['score'])
            high_grades[email] = max(high_grades.get(email,0), score)
        print("These students have a 5.0:")
        count = 0
        for (email,score) in high_grades.items():
            if score==5.0:
                print(email,score)
                count += 1
        print("Count:",count)
        print()
        print("These students have less than a 5.0 and will receive a forced grading:")
        count = 0
        for (email,score) in high_grades.items():
            if score<5.0:
                print(email,score)
                home.queue_grade(email, args.lab, message)
                count += 1
        print("Count:",count)
        sys.exit(0)

    home.queue_grade(args.email,args.lab, message)

def ssh_access(args):
    (_,api) = update_path()

    pem_key = api.get_pkey_pem("cscie-bot")
    smashed_email = smash_email(args.email)
    hostname = f"{smashed_email}.csci-e-11.org"

    # Start ssh-agent and get its environment variables
    try:
        result = subprocess.run(['ssh-agent', '-s'], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error: Failed to start ssh-agent: {e}")
        sys.exit(1)
    except FileNotFoundError:
        print("Error: ssh-agent not found. Please ensure OpenSSH is installed.")
        sys.exit(1)

    # Parse the ssh-agent output to get SSH_AUTH_SOCK and SSH_AGENT_PID
    agent_env = {}
    for line in result.stdout.split('\n'):
        line = line.strip()
        if '=' in line and line.startswith('SSH_'):
            # Parse lines like: SSH_AUTH_SOCK=/tmp/ssh-XXX/agent.123; export SSH_AUTH_SOCK;
            parts = line.split(';')[0].split('=', 1)
            if len(parts) == 2:
                agent_env[parts[0]] = parts[1]

    if 'SSH_AUTH_SOCK' not in agent_env or 'SSH_AGENT_PID' not in agent_env:
        print("Error: Failed to parse ssh-agent environment variables")
        sys.exit(1)

    try:
        # Add the private key to the agent via stdin (never touches disk)
        with subprocess.Popen(
            ['ssh-add', '-'],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **agent_env},
            text=True
        ) as ssh_add_proc:
            _, stderr = ssh_add_proc.communicate(input=pem_key)

            if ssh_add_proc.returncode != 0:
                print(f"Error adding key to ssh-agent: {stderr}")
                sys.exit(1)

        print(f"Connecting to ubuntu@{hostname}")

        # Run ssh with the agent environment (allows interactive terminal use)
        ssh_proc = subprocess.run(
            ['ssh', f'ubuntu@{hostname}'],
            env={**os.environ, **agent_env},
            check=False
        )

        sys.exit(ssh_proc.returncode)

    finally:
        # Clean up: kill the ssh-agent
        if 'SSH_AGENT_PID' in agent_env:
            try:
                os.kill(int(agent_env['SSH_AGENT_PID']), signal.SIGTERM)
            except (ValueError, ProcessLookupError, OSError):
                pass  # Best effort cleanup
