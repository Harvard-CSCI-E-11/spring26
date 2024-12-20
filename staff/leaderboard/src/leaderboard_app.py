"""
Leaerboard Fask Application (src/app.py)
"""
import time
import os
import logging
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from boto3.dynamodb.conditions import Key
import botocore.exceptions
import boto3

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=TEMPLATE_DIR)
dynamodb = boto3.resource( 'dynamodb')
leaderboard_table = dynamodb.Table(os.environ.get('LEADERBOARD_TABLE', 'Leaderboard'))
app.logger.setLevel(logging.DEBUG)

# pylint: disable=missing-function-docstring

@app.template_filter('datetimeformat')
def datetimeformat(value):
    return datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')

@app.route('/client.html', methods=['GET'])
def client():
    return render_template('client.html')

@app.route('/', methods=['GET'])
def display_leaderboard():      # pylint disable=missing-function-docstring
    try:
        response = leaderboard_table.scan()
    except botocore.exceptions.ClientError as e:
        return render_template('client_error.html', error=str(e))
    items = response['Items']

    # Separate active and inactive
    now = time.time()
    active = [item for item in items if now - item['last_seen'] < 3600]
    inactive = [item for item in items if now - item['last_seen'] >= 3600]

    # Sort by most recent last_seen
    active.sort(key=lambda x: x['last_seen'], reverse=True)

    return render_template('leaderboard.html', active=active, inactive=inactive)

@app.route('/api/update', methods=['POST'])
def update_leaderboard():   # pylint disable=missing-function-docstring
    name = request.form['name']
    key = request.form['key']
    ip_address = request.remote_addr

    app.logger.info("name=%s key=%s ip=%s",name,key,ip_address)

    if not name or not key:
        return "Invalid data", 400

    # Check if the name-key pair exists
    response = leaderboard_table.query(
        KeyConditionExpression=Key('Name').eq(name) & Key('Key').eq(key)
    )
    items = response.get('Items', [])

    if items:
        # Update existing item if IP address hasn't changed
        leaderboard_table.update_item(
            Key={'Name': name, 'Key': key},
            UpdateExpression="SET last_seen = :last_seen, ip_address = :ip_address",
            ExpressionAttributeValues={
                ':last_seen': time.time(),
                ':ip_address': ip_address
            }
        )
        # If IP address changed, also update first_seen
    else:
        # Add new item
        leaderboard_table.put_item(
            Item={
                'Name': name,
                'Key': key,
                'ip_address': ip_address
            }
        )


    # Prune old entries
    response = leaderboard_table.scan()
    items = response['Items']
    if len(items) > 100:
        items.sort(key=lambda x: x['FirstSeen'])
        to_delete = items[:len(items) - 100]
        for item in to_delete:
            leaderboard_table.delete_item(Key={'Name': item['Name'], 'Key': item['Key']})

    return 'OK', 200

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():  # pylint disable=missing-function-docstring
    response = leaderboard_table.scan()
    return jsonify(response['Items'])
