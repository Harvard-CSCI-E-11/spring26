"""
Leaerboard Fask Application (src/app.py)
"""
import time
import os
import logging
import random
from datetime import datetime
from os.path import dirname
from functools import lru_cache

from flask import Flask, request, jsonify, render_template, abort
from werkzeug.middleware.proxy_fix import ProxyFix
from botocore.exceptions import ClientError
import boto3
from itsdangerous import Serializer,BadSignature,BadData

__version__ = '0.9.2'

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
INACTIVE_SECONDS = 120
DEFAULT_LEADERBOARD_TABLE = 'Leaderboard'

dynamodb = boto3.resource( 'dynamodb')
leaderboard_table = dynamodb.Table(os.environ.get('LEADERBOARD_TABLE', DEFAULT_LEADERBOARD_TABLE))
SECRET_KEY = 'to be changed'    # for its dangerous
MAX_ITEMS = 20                  # keep it exciting
NO_MESSAGE = None

app = Flask(__name__, template_folder=TEMPLATE_DIR)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
app.logger.setLevel(logging.DEBUG)

@app.template_filter('datetimeformat')
def datetimeformat(value):
    """Format for displaying datetime in jinja2"""
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

# pylint: disable=missing-function-docstring
NOUNS = os.path.join( dirname(__file__), 'nouns.txt' )
ADJECTIVES = os.path.join( dirname(__file__), 'adjectives.txt' )

# Get a list of words from a file
def wordlist(fn):
    with open(fn,'r',encoding='utf-8') as f:
        return f.read().split('\n')

@lru_cache(maxsize=1)
def get_nouns():
    return wordlist( NOUNS )

@lru_cache(maxsize=1)
def get_adjectives():
    return wordlist( ADJECTIVES )

def random_name():
    return random.choice(get_adjectives()) + " " + random.choice(get_nouns())

def get_serializer():
    """
    Returns an itsdangerous serializer/deserializer for signed items. For info, see:
    https://itsdangerous.palletsprojects.com/en/stable/serializer/
    """
    return Serializer(SECRET_KEY)

def sort_leaders(leaders):
    """Sort the leaders oldest .. youngest.
    Python passes a reference, so we can sort in place with this.
    """
    leaders.sort(key = lambda leader:leader['first_seen'])


def get_leaderboard():
    """
    Get the leaders in the leaderboard.
    Note if they are active or inactive.
    Return sorted by active, inactive, and then by when they were first seen
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
    now = int(time.time())
    for leader in leaders:
        leader['active'] = (now - leader.get('last_seen',0)) < INACTIVE_SECONDS

    # Now sort by age
    sort_leaders(leaders)

    return leaders

@app.route('/ver', methods=['GET'])
def app_ver():
    return __version__

@app.route('/', methods=['GET'])
def display_leaderboard():      # pylint disable=missing-function-docstring
    """Route for web browsers:
    Getting / returns the HTML leaderboard pre-rendered with the leaders.
    """
    try:
        leaders = get_leaderboard()
    except ClientError as e:
        return render_template('client_error.html', error=str(e))

    # Separate active and inactive
    active   = [leader for leader in leaders if leader['active']]
    inactive = [leader for leader in leaders if not leader['active']]

    return render_template('leaderboard.html', active=active, inactive=inactive, ip_address=request.remote_addr)

@app.route('/api/register', methods=['GET'])
def api_register():
    """Return the registration of the name and secret key. Store hashed key in database"""
    s = get_serializer()
    name        = random_name()
    first_seen  = int(time.time())
    opaque = s.dumps({'name':name,
                      'first_seen':first_seen})
    return jsonify({'name':name,
                    'opaque':opaque})


# pylint: disable=too-many-locals
@app.route('/api/update', methods=['POST'])
def update_leaderboard():   # pylint disable=missing-function-docstring
    now = int(time.time())
    s = get_serializer()
    opaque   = request.form['opaque']
    try:
        data      = s.loads(opaque)
    except (BadSignature,BadData,KeyError) as e:
        abort(404, 'data tampered: '+str(e))

    ip_address = request.remote_addr
    app.logger.info("data=%s",data)

    # create the potential leaderboard object for this leader
    this_leader = {'name':data['name'],
                   'first_seen':int(data['first_seen']),
                   'last_seen':now,
                   'ip_address':ip_address}

    # Get the leaderboard
    app.logger.debug("this_leader=%s",this_leader)
    leaders = get_leaderboard()

    # If the number of leaders on the leaderboard is more than MAX_ITEMS, delete all the inactives
    to_delete = []
    if len(leaders) > MAX_ITEMS:
        to_delete.extend([leader for leader in leaders if not leader['active']])
        leaders = [leader for leader in leaders if leader['active']]

    # Write this_leader to the leaderboard if:
    # - There are less than MAX_ITEMS on the leaderboard
    # - This is older than the youngest on the leaderboard
    if leaders:
        youngest_leader = max( (leader['first_seen'] for leader in leaders) )
    else:
        youngest_leader = now

    # Add this leader to the leaderboard if this leader not there
    if ( this_leader['first_seen'] < youngest_leader) or (len(leaders) < MAX_ITEMS):
        try:
            leaderboard_table.put_item(Item=this_leader) # replaces if already there
        except ClientError as err:
            app.logger.error(
                "Couldn't put_item on leaders: %s: %s",
                err.response['Error']['Code'],
                err.response['Error']['Message']
            )
            raise
        if this_leader['name'] not in set( (leader['name'] for leader in leaders) ):
            this_leader['active'] = True
            leaders.append(this_leader)

    # If the number of leaders on the leaderboard is still n more than MAX_ITEMS,
    # delete the youngest N items
    sort_leaders(leaders)
    n = len(leaders) - MAX_ITEMS
    if n>0:
        to_delete.extend(leaders[:-n])
        leaders = leaders[-n:]

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

    # and return to the caller
    return jsonify({'leaderboard':leaders,'message':NO_MESSAGE, 'now':now})


@app.route('/api/leaderboard', methods=['GET'])
def api_leaderboard():
    return jsonify( {'leaderboard':get_leaderboard(),
                     'message':NO_MESSAGE})
