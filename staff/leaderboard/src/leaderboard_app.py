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
INACTIVE_SECONDS = 300
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
    now = int(time.time())
    active = [item for item in items if now - item['last_seen'] < INACTIVE_SECONDS]
    inactive = [item for item in items if now - item['last_seen'] >= INACTIVE_SECONDS]

    # Sort by most recent last_seen
    active.sort(key=lambda x: x['last_seen'], reverse=True)

    return render_template('leaderboard.html', active=active, inactive=inactive)

@app.route('/api/update', methods=['POST'])
def update_leaderboard():   # pylint disable=missing-function-docstring
    name = request.form['name']
    hidden = request.form['hidden']
    ip_address = request.remote_addr
    now = int(time.time())

    app.logger.info("name=%s hidden=%s ip=%s",name,hidden,ip_address)

    if not name or not hidden:
        return "Invalid data", 400

    # Check if the name exists
    response = leaderboard_table.query( KeyConditionExpression=Key('name').eq(name) )
    items = response.get('Items', [])
    updated = False
    for i in items:
        # If we find a matching name and the key doesn't match, return
        # If the key does match, update last seen. If ip address doesn't match, update first-seen
        if i['name']==name:
            if i['hidden'] != hidden:
                return "Hidden mismatch", 403
            if i['ip_address'] == ip_address:
                leaderboard_table.update_item(
                    Key={'name': name},
                    UpdateExpression="SET last_seen = :last_seen",
                    ExpressionAttributeValues={
                        ':last_seen': now,
                    })
            else:
                leaderboard_table.update_item(
                    Key={'name': name},
                    UpdateExpression="SET last_seen = :last_seen, first_seen = :fist_seen, ip_address = :ip_address",
                    ExpressionAttributeValues={
                        ':last_seen': now,
                        ':first_seen': now,
                        ':ip_address': ip_address
                    })
            updated = True
    # If nothing was updated, add the new entry
    if not updated:
        leaderboard_table.put_item(
            Item={
                'name': name,
                'hidden': hidden,
                'ip_address': ip_address,
                'last_seen': now,
                'first_seen': now
            }
        )


    # Prune old entries
    response = leaderboard_table.scan()
    items = response['Items']
    if len(items) > 100:
        items.sort(key=lambda x: x['first_seen'])
        to_delete = items[:len(items) - 100]
        for item in to_delete:
            leaderboard_table.delete_item(Key={'Name': item['Name']})

    return 'OK', 200

@app.route('/api/leaderboard', methods=['GET'])
def get_leaderboard():  # pylint disable=missing-function-docstring
    response = leaderboard_table.scan()
    return jsonify(response['Items'])
