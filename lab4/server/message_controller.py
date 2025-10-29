"""
message_controller: implements a simple message server where new
messages must be authenticated but anyone can view.

"""

from flask import request, abort
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

def validate_api_key_request():
    """Validate the API_KEY and API_SECRET_KEY for the current Flask request.
    Abort if invalid. Return the api_key_id if valid
    :returns: api_key_id of the api_key if the api_key and api_secret_key are valid.

    """
    api_key         = request.values.get('api_key', type=str, default="")
    if not api_key:
        abort(401, description='api_key not provided')

    api_secret_key  = request.values.get('api_secret_key', type=str, default="")
    if not api_secret_key:
        abort(401, description='api_secret_key not provided')

    # Verify api_key and api_secret_key
    return apikey.validate_api_key(api_key, api_secret_key)

def init_app(app):
    """Initialize the app and register the paths."""

    @app.route('/api/post-message', methods=['POST'])
    def api_post_message():
        api_key_id = validate_api_key_request()
        post_message(api_key_id, request.values.get('message'))
        return "OK",200

    @app.route('/api/get-messages', methods=['GET'])
    def api_get_messages():
        # Get the messages and expand every sqlite3.Row object into a dictionary
        return [dict(message) for message in get_messages()]
