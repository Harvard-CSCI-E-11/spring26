"""
Leaerboard Fask Application (src/app.py)
"""
from flask import Flask, request, jsonify, render_template
from boto3.dynamodb.conditions import Key
import botocore.exceptions
import boto3
import time
import os
import logging
import sys
from datetime import datetime, timedelta

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates')
app = Flask(__name__, template_folder=TEMPLATE_DIR)
dynamodb = boto3.resource(
    'dynamodb',
    region_name=os.environ.get('AWS_REGION', 'us-east-1')
)
leaderboard_table = dynamodb.Table(os.environ.get('LEADERBOARD_TABLE', 'Leaderboard'))


dynamodb = boto3.resource('dynamodb')
leaderboard_table = dynamodb.Table(os.environ.get('LEADERBOARD_TABLE', 'Leaderboard'))

@app.route('/client.html', methods=['GET'])
def client():
    return render_template('client.html')

@app.route('/', methods=['GET'])
def display_leaderboard():
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
def update_leaderboard():
    name = request.form['name']
    key = request.form['key']
    ip = request.remote_addr

    if not name or not key:
        return "Invalid data", 400

    now = datetime.utcnow().isoformat()

    # Check if the name-key pair exists
    response = leaderboard_table.query(
        KeyConditionExpression=Key('name').eq(name) & Key('key').eq(key)
    )
    items = response.get('Items', [])

    if items:
        # Update existing item if IP address hasn't changed
        leaderboard_table.update_item(
            Key={'name': name, 'key': key},
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
                'name': name,
                'key': key,
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
def get_leaderboard():
    response = leaderboard_table.scan()
    return jsonify(response['Items'])
