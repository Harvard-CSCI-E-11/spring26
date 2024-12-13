"""
db.py: database management routines.
This uses a SQLite3 database. For a system serving multiple users simultaneously,
use MySQL or DynamoDB instead.
"""

import sqlite3
from datetime import datetime

import click
from flask import current_app, g

sqlite3.register_converter(
    "timestamp", lambda v: datetime.fromisoformat(v.decode())
)

def get_db():
    """Return a database connection"""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
    return g.db

def close_db(e=None):
    """Close the database connection"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize the database"""
    db = get_db()
    with current_app.open_resource('schema.sql') as f:
        db.executescript(f.read().decode('utf8'))

def list_images():
    """Return an array of dicts for all the images"""
    db = get_db()
    return db.execute('select * from images')

def get_image_info(image_id):
    """Return a dict for a specific image"""
    db = get_db()
    return db.execute('select * from images where image_id=?',(image_id,)).fetchone()

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


def init_app(app):
    """Initialize"""
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
