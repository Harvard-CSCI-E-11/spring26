"""
db.py: database management routines.
This uses a SQLite3 database. For a system serving multiple users simultaneously,
use MySQL or DynamoDB instead.
"""

import sqlite3
from datetime import datetime

import tabulate
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

# pylint: disable=unused-argument
def close_db(e=None):
    """Close the database connection if one was set through g.db=<foo>"""
    db = g.pop('db', None)
    if db is not None:
        db.close()

def init_db():
    """Initialize the database by loading every file that begins 'schema' and ends '.sql'"""
    db = get_db()
    app_directory = app.root_path
    for fname in os.listdir(app_directory):
        if fname.startswith('schema') and fname.endswith('.sql'):
            with current_app.open_resource(fname) as f:
                db.executescript(f.read().decode('utf8'))

@click.command('init-db')
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo('Initialized the database.')


@click.command("dump-db")
def dump_db_command():
    """Dump the contents of the database"""
    db = get_db()
    cur = db.cursor()
    # Get a list of tables
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

    # Now list each table
    for row in tables:
        table_name = row['name']
        click.echo(f"Table: {table_name}")
        # Note we can't prepare the table name in the statement below
        rows = cur.execute(f"SELECT * FROM {table_name}").fetchall()
        if not rows:
            click.echo("Database is empty")
        else:
            header = rows[0].keys()
            click.echo(tabulate.tabulate(rows,header))

def init_app(app):
    """Initialize"""
    # always call close_db when connection is finished.
    app.teardown_appcontext(close_db)

    # Register CLI commands
    app.cli.add_command(init_db_command)
    app.cli.add_command(dump_db_command)
