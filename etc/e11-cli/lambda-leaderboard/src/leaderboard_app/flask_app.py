"""
Leaerboard Fask Application (src/app.py).
"""
import time
import os
import logging
import random
from datetime import datetime
from os.path import dirname
from functools import lru_cache
import base64

from flask import Flask, request, jsonify, render_template, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from botocore.exceptions import ClientError
import boto3
from itsdangerous import Serializer,BadSignature,BadData

from e11.e11_common import (get_user_from_email, get_grade, add_grade, send_email)
from e11.e11core import grader

__version__ = '0.9.3'

BASE_SCORE = 4.5
SCORE_WITH_MAGIC = 5.
MAGIC = 'magic'
LAB='lab7'

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
INACTIVE_SECONDS = 120
DEFAULT_LEADERBOARD_TABLE = 'Leaderboard'

# Use local DynamoDB endpoint if specified
dynamodb_endpoint = os.environ.get('AWS_ENDPOINT_URL_DYNAMODB')
if dynamodb_endpoint:
    dynamodb = boto3.resource('dynamodb', endpoint_url=dynamodb_endpoint)
else:
    dynamodb = boto3.resource('dynamodb')
leaderboard_table = dynamodb.Table(os.environ.get('LEADERBOARD_TABLE', DEFAULT_LEADERBOARD_TABLE))
SECRET_KEY = 'to be changed'    # for its dangerous
MAX_ITEMS = 100                 # we have 90 students in the class
NO_MESSAGE = None

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.logger.setLevel(logging.DEBUG)

@app.before_request
def _log_path():
    app.logger.info("PATH_INFO=%r script_root=%r full_path=%r",
                    request.environ.get("PATH_INFO"),
                    request.script_root,
                    request.full_path)


@app.template_filter('datetimeformat')
def datetimeformat(value):
    """Format for displaying datetime in jinja2"""
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

# pylint: disable=missing-function-docstring
NOUNS = os.path.join( dirname(__file__), 'nouns.txt' )
ADJECTIVES = os.path.join( dirname(__file__), 'adjectives.txt' )

# Get a list of words from a file
def wordlist(fn):
    """Given a file, return all of its lines as an array."""
    with open(fn,'r',encoding='utf-8') as f:
        return f.read().split('\n')

@lru_cache(maxsize=1)
def get_nouns():
    """Return the list of nouns."""
    return wordlist( NOUNS )

@lru_cache(maxsize=1)
def get_adjectives():
    """Return the list of adjectives."""
    return wordlist( ADJECTIVES )

def random_name():
    """make a random ADJECTIVE NOUN name"""
    return random.choice(get_adjectives()) + " " + random.choice(get_nouns())

def get_serializer():
    """
    Returns an itsdangerous serializer/deserializer for signed items. For info, see:
    https://itsdangerous.palletsprojects.com/en/stable/serializer/
    """
    return Serializer(SECRET_KEY)

def sorted_leaders(leaders):
    """Sort the leaders oldest .. youngest.
    Python passes a reference, so we can sort in place with this.
    """
    leaders.sort(key = lambda leader:leader['first_seen'])
    return leaders

def leader_is_active(leader):
    """Return true if a leader is active"""
    now = int(time.time())
    return (now - int(leader.get('last_seen',0))) < INACTIVE_SECONDS

def get_leaderboard():
    """
    Get the leaders in the leaderboard.
    Note if each is active or inactive.
    Return sorted by when first seen.
    """
    try:
        leaders = []
        start_key = None
        scan_kwargs = {}
        while True:
            if start_key:
                scan_kwargs['ExclusiveStartKey'] = start_key
            response = leaderboard_table.scan(**scan_kwargs)
            app.logger.debug("response=%s",response)
            leaders.extend(response.get('Items', []))
            start_key = response.get('LastEvaluatedKey', None)
            if start_key is None:
                break
    except ClientError as err:
        app.logger.error(
            "Couldn't scan for leaders: %s: %s",
            err.response['Error']['Code'],
            err.response['Error']['Message']
        )
        raise

    # Convert DynamoDB responses to a bunch of dictionaries
    leaders = [dict(leader) for leader in leaders]

    # Figure out who is active and inactive
    for leader in leaders:
        leader['active'] = leader_is_active(leader)

    return sorted_leaders(leaders)


def update_leaderboard(*,data,ip_address,user_agent):
    """Given a name that's already been validated,
    update the leaderboard, and return the new leaders"""

    # create the potential leaderboard object for this leader
    now = int(time.time())
    this_leader = {'name':data['name'],
                   'first_seen':int(data['first_seen']),
                   'last_seen':now,
                   'ip_address':ip_address,
                   'user_agent':user_agent}
    app.logger.debug("this_leader=%s",this_leader)

    # Update this leader on the leaderboard
    try:
        leaderboard_table.put_item(Item=this_leader) # replaces if already there
    except ClientError as err:
        app.logger.error(
            "Couldn't put_item on leaders: %s: %s",
            err.response['Error']['Code'],
            err.response['Error']['Message']
        )
        raise

    # Get the leaderboard (will include this_leader, and this_leader should be active)
    leaders = get_leaderboard()

    me = [leader for leader in leaders if leader['name']==this_leader['name']]
    assert len(me)==1
    assert me[0]['active'] is True


    # If the number of leaders on the leaderboard is more than MAX_ITEMS, delete all the inactives
    to_delete = []
    if len(leaders) > MAX_ITEMS:
        to_delete.extend([leader for leader in leaders if not leader['active']])
        leaders = [leader for leader in leaders if leader['active']]

    # Delete all in to_delete from DynamoDB
    try:
        with leaderboard_table.batch_writer() as batch:
            for leader in to_delete:
                batch.delete_item(Key={'name':leader['name']})
    except ClientError as err:
        app.logger.error(
            "Couldn't delete_item on leaders: %s: %s",
            err.response['Error']['Code'],
            err.response['Error']['Message']
        )
        raise
    return leaders


def new_registration():
    """Returns a new registration consisting of a signed name and first_seen."""
    s = get_serializer()
    name        = random_name()
    first_seen  = int(time.time())
    opaque = s.dumps({'name':name,
                      'first_seen':first_seen})
    return {'name':name,
            'opaque':opaque}

def validate_registration(opaque):
    """Validate the opaque registration nonce and return its content."""
    try:
        s = get_serializer()
        data = s.loads(opaque)
        app.logger.info("data=%s",data)
        return data
    except (BadSignature,BadData,KeyError) as e:
        abort(404, 'data tampered: '+str(e))

@app.route('/ver', methods=['GET'])
def app_ver():
    return __version__

@app.route('/')
def root():
    """Return the leaderboard page"""
    # Read and encode the icon
    icon_path = os.path.join(os.path.dirname(__file__), 'icon.png')
    with open(icon_path, 'rb') as f:
        icon_data = base64.b64encode(f.read()).decode('utf-8')

    # Get the IP address
    if request.headers.get('X-Forwarded-For'):
        ip_address = request.headers.get('X-Forwarded-For').split(',')[0]
    else:
        ip_address = request.remote_addr

    return render_template('leaderboard.html',
                         ip_address=ip_address,
                         FAVICO=icon_data)

@app.route('/api/register', methods=['GET'])
def api_get_register():
    """Return the registration of the name and secret key. Store hashed key in database"""
    return  jsonify(new_registration())

@app.route('/api/register', methods=['POST'])
def api_post_register():
    """Check the posted email and class key. If they are correct, grade the assignment.
    Then return the registration of the name and secret key. Store hashed key in database"""
    email = request.form.get('email','')
    course_key = request.form.get('course_key','')

    user = get_user_from_email(email)
    if not user:
        abort(404, 'invalid email')
    if user.course_key != course_key:
        abort(404, 'invalid course_key')

    user_agent = str(request.user_agent)
    pass_names = ['test_user_key']
    if MAGIC.lower() in user_agent.lower():
        score = SCORE_WITH_MAGIC
        pass_names = ['test_agent_string']
        fail_names = []
    else:
        score = BASE_SCORE
        fail_names = ['test_agent_string']

    # if score is higher than current score, record that
    old_score = get_grade(user, LAB)
    if old_score < score:
        summary = {'score':score,
                   'pass_names':pass_names,
                   'fail_names':fail_names,
                   'raw':''}

        add_grade(user, LAB, request.remote_addr, summary)
        (subject, body) = grader.create_email(summary)
        send_email(to_addr = user.email,
                   email_subject = subject,
                   email_body=body)


    return  jsonify(new_registration())

@app.route('/api/update', methods=['POST'])
def api_update():   # pylint disable=missing-function-docstring
    now = int(time.time())      # because callers may not have reliable time
    data = validate_registration(request.form['opaque'])
    leaders = update_leaderboard(data=data, ip_address=request.remote_addr,
                                 user_agent=str(request.user_agent))
    # and return to the caller
    return jsonify({'leaderboard':leaders,'message':NO_MESSAGE, 'now':now})
