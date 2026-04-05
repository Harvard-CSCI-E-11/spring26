
"""
e11 staff commands.
"""

import sys
import os
import time
import csv
import json
import re
import subprocess
import signal
import functools
from typing import Any, Dict, List
from decimal import Decimal

import dns.resolver
from tabulate import tabulate
import boto3
from boto3.dynamodb.conditions import Attr
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from e11.e11core.e11ssh import E11Ssh
from e11.e11core.grader import print_summary
from e11.e11core.utils import smash_email
from e11.e11core.constants import COURSE_DOMAIN
from e11.e11_common import (dynamodb_client,dynamodb_resource,A,create_new_user,users_table,add_user_log,
                            get_user_from_email,queryscan_table,generate_direct_login_url,EmailNotRegistered,
                            select_highest_grade_records)

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

def do_edit_email(args):
    try:
        user = get_user_from_email(args.email)
    except EmailNotRegistered:
        print(f"Email {args.email} is not registered")
        sys.exit(1)
    if args.alt:
        users_table.update_item( Key={ 'user_id': user.user_id,
                                       'sk': '#'},
                                 UpdateExpression="SET alt_email= :alt",
                                 ExpressionAttributeValues={':alt':args.alt})
        add_user_log( None, user.user_id, f"User alt_email updated to {args.alt}")
    elif args.remove:
        users_table.update_item( Key={ 'user_id': user.user_id,
                                       'sk': '#'},
                                 UpdateExpression="REMOVE alt_email")
        add_user_log( None, user.user_id, "User alt_email removed")


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


################################################################

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

    # Get all of the registration records
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
## Compute, Print and upload student grades

def get_items(whowhat):
    """Return either the grades for a lab or a person. Returns all, not just the highest"""
    if whowhat.startswith("lab"):
        kwargs:dict = {
            'FilterExpression' : ( Key(A.SK).begins_with(f'{A.SK_GRADE_PREFIX}{whowhat}#') ),
            'ProjectionExpression' : f'{A.USER_ID}, {A.SK}, {A.SCORE}',
        }
        return queryscan_table(users_table.scan, kwargs)

    # Get all the records for the student
    user = get_user_from_email(whowhat)
    for (k,v) in sorted(dict(user).items()):
        print(f"{k}:{v}")

    kwargs:dict = {'KeyConditionExpression' : (
        Key(A.USER_ID).eq(user.user_id) &
        Key(A.SK).begins_with(A.SK_GRADE_PREFIX)
    )}
    return queryscan_table(users_table.query, kwargs)


def get_highest_grades(items):
    """Given a list of grades, return a list of only the highest grade for each student and each lab"""
    return select_highest_grade_records(items)


def print_grades(items, args):
    print(f"print_grades(len(items)={len(items)} args={args}")

    if not args.all:
        items = get_highest_grades(items)
    else:
        print("Removing all but highest grades")

    all_grades = [(userid_to_email(r[A.USER_ID]), # email row[0]
                   r[A.SK].split('#')[1],         # lab  row[1]
                   Decimal(r[A.SCORE]),           # score row[2]
                   r[A.SK].split('#')[2],         # date row[3]
                   r[A.USER_ID])                  # user_id row[4]
                  for r in items if r[A.SK].count('#')==2]

    if args.claims:
        # remove grades for which there are no claims
        all_grades = [row for row in all_grades if userid_to_user().get(row[4], {}).get('claims')]

    all_grades.sort()
    # Now print
    print(tabulate(all_grades))
    print("Total:",len(all_grades))

def do_print_grades(args):
    items = get_items(args.whowhat)
    print_grades(items, args)


def _lab_sort_key(lab: str) -> tuple[int, str]:
    try:
        return (int(lab.replace("lab", "")), lab)
    except ValueError:
        return (9999, lab)


def _grade_timestamp(item: Dict[str, Any]) -> str:
    return str(item.get(A.SK, "")).split("#", 2)[2]


def _item_timestamp(item: Dict[str, Any]) -> str:
    sk = str(item.get(A.SK, ""))
    parts = sk.split("#", 2)
    return parts[-1] if parts else sk


def _display_timestamp(timestamp: str, show_msec: bool) -> str:
    timestamp = timestamp.replace("T", " ")
    if show_msec:
        return timestamp
    if "." in timestamp:
        return timestamp.split(".", 1)[0]
    return timestamp


def _grade_score(item: Dict[str, Any]) -> Decimal:
    return Decimal(str(item.get(A.SCORE, 0)))


def _format_score(score: Decimal) -> str:
    return f"{float(score):.1f}"


def _safe_load_grade_summary(item: Dict[str, Any]) -> Dict[str, Any] | None:
    raw = item.get("raw")
    if not raw:
        return None
    try:
        summary = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return summary if isinstance(summary, dict) else None


def _user_grade_items(email: str) -> List[Dict[str, Any]]:
    user = get_user_from_email(email)
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": (
            Key(A.USER_ID).eq(user.user_id) &
            Key(A.SK).begins_with(A.SK_GRADE_PREFIX)
        )
    }
    return queryscan_table(users_table.query, kwargs)


def _user_all_items(user_id: str) -> List[Dict[str, Any]]:
    kwargs: dict[str, Any] = {
        "KeyConditionExpression": Key(A.USER_ID).eq(user_id)
    }
    return queryscan_table(users_table.query, kwargs)


def _format_epoch_timestamp(value: Any) -> str:
    try:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(int(value)))
    except (TypeError, ValueError, OSError):
        return str(value)


def _extract_ip_history(user: Any, items: List[Dict[str, Any]], show_msec: bool) -> List[List[str]]:
    history: list[tuple[str, str, str]] = []

    if getattr(user, "public_ip", None) and getattr(user, "host_registered", None):
        history.append((
            _format_epoch_timestamp(user.host_registered),
            str(user.public_ip),
            "user record",
        ))

    for item in items:
        sk = str(item.get(A.SK, ""))
        if sk.startswith(A.SK_LOG_PREFIX):
            message = str(item.get("message", ""))
            match = re.search(r"public_ip=([0-9.]+)", message)
            if match:
                history.append((_item_timestamp(item), match.group(1), "registration log"))
        elif sk.startswith(A.SK_GRADE_PREFIX):
            grade_ip = item.get(A.PUBLIC_IP)
            if grade_ip:
                history.append((_grade_timestamp(item), str(grade_ip), "grade record"))

    history.sort()
    rows: list[list[str]] = []
    seen = set()
    for row in history:
        if row in seen:
            continue
        seen.add(row)
        rows.append([_display_timestamp(row[0], show_msec), row[1], row[2]])
    return rows


def _primary_dns_name(user: Any) -> str | None:
    hostname = getattr(user, "hostname", None)
    if not hostname and getattr(user, "email", None):
        hostname = smash_email(user.email)
    if not hostname:
        return None
    return f"{hostname}.{COURSE_DOMAIN}"


def _resolve_primary_dns(fqdn: str) -> str:
    try:
        answers = dns.resolver.resolve(fqdn, "A")
        return ", ".join(sorted({str(answer) for answer in answers}))
    except Exception as exc:  # noqa: BLE001 pylint: disable=broad-exception-caught
        return f"lookup failed: {exc}"


def _run_primary_ping(fqdn: str):
    cmd = ["ping", "-c", "5", fqdn]
    print("Ping command:")
    print(" ".join(cmd))
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
    except subprocess.TimeoutExpired:
        print("ping timed out after 10 seconds")
        print("")
        return
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    print("")


def _print_primary_dns(user: Any):
    fqdn = _primary_dns_name(user)
    if not fqdn:
        return
    print("Primary DNS:")
    print(tabulate([[fqdn, _resolve_primary_dns(fqdn)]], headers=["hostname", "current A record"], disable_numparse=True))
    print("")
    _run_primary_ping(fqdn)


def _print_ip_history(user: Any, items: List[Dict[str, Any]], show_msec: bool):
    rows = _extract_ip_history(user, items, show_msec)
    if not rows:
        return
    print("IP history:")
    print(tabulate(rows, headers=["when", "ip address", "source"], disable_numparse=True))
    print("")


def _extract_lifecycle_events(items: List[Dict[str, Any]], show_msec: bool) -> List[List[str]]:
    rows: list[list[str]] = []
    for item in items:
        sk = str(item.get(A.SK, ""))
        if not sk.startswith(A.SK_LOG_PREFIX):
            continue
        message = str(item.get("message", ""))
        event_type = str(item.get("event_type", ""))
        source = str(item.get("source", ""))
        public_ip = str(item.get("public_ip", ""))
        instance_id = str(item.get("instanceId", ""))

        if not event_type:
            if message.startswith("User registered"):
                event_type = "register"
                source = source or ("boot-service" if "source=boot-service" in message else "cli")
                public_ip_match = re.search(r"public_ip=([0-9.]+)", message)
                instance_id_match = re.search(r"instanceId=([^ ]+)", message)
                public_ip = public_ip or (public_ip_match.group(1) if public_ip_match else "")
                instance_id = instance_id or (instance_id_match.group(1) if instance_id_match else "")
            elif message.startswith("Shutdown reported"):
                event_type = "shutdown"
                source = source or ("boot-service" if "source=boot-service" in message else "cli")
                public_ip_match = re.search(r"public_ip=([0-9.]+)", message)
                instance_id_match = re.search(r"instanceId=([^ ]+)", message)
                public_ip = public_ip or (public_ip_match.group(1) if public_ip_match else "")
                instance_id = instance_id or (instance_id_match.group(1) if instance_id_match else "")

        if event_type not in {"register", "shutdown"}:
            continue

        rows.append([
            _display_timestamp(_item_timestamp(item), show_msec),
            event_type,
            source,
            public_ip,
            instance_id,
            message,
        ])
    rows.sort()
    return rows


def _print_lifecycle_events(items: List[Dict[str, Any]], show_msec: bool):
    rows = _extract_lifecycle_events(items, show_msec)
    if not rows:
        return
    print("Lifecycle events:")
    print(tabulate(
        rows,
        headers=["when", "event", "source", "ip address", "instanceId", "message"],
        disable_numparse=True,
    ))
    print("")


def _grade_attempt_row(item: Dict[str, Any], show_msec: bool) -> List[Any]:
    summary = _safe_load_grade_summary(item) or {}
    passes = summary.get("passes", item.get("pass_names", []))
    fails = summary.get("fails", item.get("fail_names", []))
    note = item.get("note", "")
    return [
        _display_timestamp(_grade_timestamp(item), show_msec),
        str(item.get(A.PUBLIC_IP, "")),
        _format_score(_grade_score(item)),
        len(passes) if isinstance(passes, list) else "n/a",
        len(fails) if isinstance(fails, list) else "n/a",
        note,
    ]


def _print_lab_attempts(lab: str, items: List[Dict[str, Any]], verbose: bool, show_msec: bool):
    rows = [_grade_attempt_row(item, show_msec) for item in items]
    print(f"\n{lab}:")
    print(tabulate(rows, headers=["graded", "student ip", "score", "passes", "fails", "note"], disable_numparse=True))
    if not verbose:
        return
    for item in items:
        summary = _safe_load_grade_summary(item)
        print(f"\n=== {lab} grading run {_display_timestamp(_grade_timestamp(item), show_msec)} ===")
        if summary is None:
            print("No raw grading summary available.")
            continue
        print_summary(summary, verbose=True)


def do_student_log(args):
    user = get_user_from_email(args.email)
    all_items = _user_all_items(user.user_id)
    _print_primary_dns(user)
    _print_lifecycle_events(all_items, args.msec)
    _print_ip_history(user, all_items, args.msec)

    items = [item for item in all_items if str(item.get(A.SK, "")).startswith(A.SK_GRADE_PREFIX)]
    if args.lab:
        items = [item for item in items if item.get(A.LAB) == args.lab]
        items.sort(key=_grade_timestamp)
        if not items:
            print(f"No grading sessions found for {args.email} {args.lab}")
            return
        _print_lab_attempts(args.lab, items, args.verbose, args.msec)
        return

    by_lab: Dict[str, List[Dict[str, Any]]] = {}
    for item in items:
        lab = str(item.get(A.LAB, "unknown"))
        by_lab.setdefault(lab, []).append(item)

    if not by_lab:
        print(f"No grading sessions found for {args.email}")
        return

    rows = []
    for lab in sorted(by_lab, key=_lab_sort_key):
        lab_items = sorted(by_lab[lab], key=_grade_timestamp)
        scores = [_grade_score(item) for item in lab_items]
        rows.append([
            lab,
            len(lab_items),
            _display_timestamp(_grade_timestamp(lab_items[0]), args.msec),
            _display_timestamp(_grade_timestamp(lab_items[-1]), args.msec),
            _format_score(scores[-1]),
            _format_score(max(scores)),
        ])
    print(tabulate(
        rows,
        headers=["lab", "sessions", "first graded", "last graded", "last grade", "highest grade"],
        disable_numparse=True,
    ))

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
    for item in get_highest_grades(get_items(args.lab)):
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

    os.environ['SSH_SECRET_ID'] = find_secret("ssh")
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
            pem_key += '\n'
            _, stderr = ssh_add_proc.communicate(input=pem_key)

            if ssh_add_proc.returncode != 0:
                print(f"Error adding key to ssh-agent: {stderr}")
                print(pem_key)
                sys.exit(1)

        print(f"Connecting to ubuntu@{hostname}")

        # Run ssh with the agent environment (allows interactive terminal use)
        ssh_proc = subprocess.run(
            ['ssh', '-o', 'IdentitiesOnly=no', f'ubuntu@{hostname}'],
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
