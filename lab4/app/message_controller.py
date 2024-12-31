"""
message_controller: implements a simple message server where new
messages must be authenticated but anyone can view.

"""

from flask import request, current_app, abort, redirect
from . import apikey
from .db import get_db

def get_messages():
    """Return an array of dicts for all the messages"""
    db = get_db()
    return db.execute('SELECT * FROM messages ORDER BY created DESC')


def post_message(api_key_id, message):
    """Add a new message in the database"""
    db = get_db()
    cur  = db.cursor()
    cur.execute("""
        INSERT into messages (created_by,message)
        VALUES (?, ?)
        """,(api_key_id, message))
    db.commit()
    return cur.lastrowid        # return the row inserted into images

def init_app(app):
    """Initialize the app and register the paths."""

    @app.route('/api/post-message', methods=['POST'])
    def api_post_message():
        api_key_id = apikey.validate_api_key_request()
        post_message(api_key_id, request.values.get('message'))
        return "OK",200

    @app.route('/api/get-messages', methods=['GET'])
    def api_get_messages():
        # Get the messages and expand every sqlite3.Row object into a dictionary
        return [dict(message) for message in get_messages()]
