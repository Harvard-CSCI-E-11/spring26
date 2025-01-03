"""
Leaerboard Fask Application (src/app.py)
"""
import time
import os
import logging
import random
from datetime import datetime
from os.path import abspath,dirname

from flask import Flask, request, jsonify, render_template, abort
from botocore.exceptions import ClientError
import boto3
from itsdangerous import Serializer,BadSignature,BadData


TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
INACTIVE_SECONDS = 120
app = Flask(__name__, template_folder=TEMPLATE_DIR)
dynamodb = boto3.resource( 'dynamodb')
leaderboard_table = dynamodb.Table(os.environ.get('LEADERBOARD_TABLE', 'Leaderboard'))
app.logger.setLevel(logging.DEBUG)
SECRET_KEY = 'to be changed'    # for its dangerous
MAX_ITEMS = 100

# pylint: disable=missing-function-docstring

# Make a list of the nouns and adjectives
def wordlist(fn):
    with open(fn,'r',encoding='utf-8') as f:
        return f.read().split('\n')

NOUNS = os.path.join( dirname(__file__), 'nouns.txt' )
ADJECTIVES = os.path.join( dirname(__file__), 'adjectives.txt' )

nouns = wordlist( NOUNS )
adjectives = wordlist( ADJECTIVES )
def random_name():
    return random.choice(nouns) + " " + random.choice(adjectives)

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
    scan_kwargs = {
        'ProjectExpression' : 'name, ip_address, first_seen, last_seen'
    }

    try:
        leaders = []
        done = False
        start_key = None
        while not done:
            if start_key:
                scan_kwargs['ExclusiveStartKey'] = start_key
            response = leaderboard_table.scan(**scan_kwargs)
            leaders.extend(response.get('Items', []))
            start_key = response.get('LastEvaluatedKey', None)
            done = start_key is None
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
    now = time.time()
    for leader in leaders:
        leader['active'] = (now - leader.get('last_seen',0)) < INACTIVE_SECONDS

    # Now sort by age
    sort_leaders(leaders)

    return leaders

@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

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
    active = [leader for leader in leaders if leader['active']]
    inactive = [leader for leader in leaders if not leader['active']]

    return render_template('leaderboard.html', active=active, inactive=inactive)

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
                   'first_seen':data['first_seen'],
                   'ip_addr':ip_address}

    # Get the leaderboard
    leaders = get_leaderboard()

    # If the number of leaders on the leaderboard is more than MAX_ITEMS, delete all the inactives
    to_delete = []
    if len(leaders) > MAX_ITEMS:
        to_delete.extend([leader for leader in leaders if not leader['active']])
        leaders = [leader for leader in leaders if leader['active']]

    # If this_leader is older than one of the leaders on the leaderboard,
    # or if the number of leaders is less than MAX_ITEMS, add this leader and resort.
    youngest_leader = max( (leader['first_seen'] for leader in leaders) )
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
        leaders.append(this_leader)
        sort_leaders(leaders)

    # If the number of leaders on the leaderboard is still n more than MAX_ITEMS, delete the oldest
    # N items
    n = len(leaders) - MAX_ITEMS
    if n>0:
        to_delete.extend(leaders[:-n])
        leaders = leaders[-n:]

    # Delete all in to_delete from DynamoDB
    try:
        with leaderboard_table.batch_writer() as batch:
            for leader in to_delete:
                response = batch.delete_item(Key={'name':leader['name']})
    except ClientError as err:
        app.logger.error(
            "Couldn't delete_item on leaders: %s: %s",
            err.response['Error']['Code'],
            err.response['Error']['Message']
        )
        raise


    # and return to the caller
    return jsonify(leaders)


@app.route('/api/leaderboard', methods=['GET'])
def api_leaderboard():
    return jsonify( get_leaderboard())
