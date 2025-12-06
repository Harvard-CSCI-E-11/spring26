"""
db.py - database management routines.

This implementation uses a SQLite3 database. For a system serving multiple users
simultaneously, you would use Postgress or DynamoDB.  Because all
database-specific code here, it is possible to change the database by
only changing this file.

The schema is loaded dynamically from all files called "schema_*.sql" in the source code directory.

(C) 2025 Simson L. Garfinkel.

STUDENTS - You do not need to modify this file.

"""

import os
import sqlite3
import glob
from datetime import datetime
from os.path import join

import tabulate
import click
from flask import current_app, g

DBFILE_NAME = "message_board.db"

#
# This allows sqlite3 to directly handle Python datetime object
# It runs when db.py is imported
#
sqlite3.register_converter("timestamp", lambda v: datetime.fromisoformat(v.decode()))

def get_lab_number():
    """Return the lab number as a string from the file name"""
    m = re.search(r"lab(\d)", __file__)
    if m:
        return m.group(1)
    return "?"                  # give a valid response


def get_lab_name():
    """Return the lab name from the file name"""
    m = re.search(r"(lab\d)", __file__)
    if m:
        return m.group(1)
    return ""                   # no lab name

def get_db_conn():
    """Return either a new database connection or the cached
    per-instance connection.

    Note that the connection is modified so all records are returned
    as dictionaries, rather than tuples.
    """
    if "db" not in g:
        g.conn = sqlite3.connect(
            current_app.config["DATABASE"], detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.conn.row_factory = sqlite3.Row
    return g.conn


# pylint: disable=unused-argument
def close_db(e=None):
    """Close the database connection if one was set through g.db=<foo>"""
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    """Initialize the database by loading every file that begins 'schema' and ends '.sql'
    current_app is set by click CLI.
    """
    conn = get_db_conn()
    app_directory = current_app.root_path
    for fname in glob.glob(join(app_directory, "schema*.sql")):
        with open(fname, "r", encoding="utf8") as f:
            conn.executescript(f.read())
            conn.commit()


@click.command("init-db")
def init_db_command():
    """Clear the existing data and create new tables."""
    init_db()
    click.echo("Initialized the database.")


@click.command("dump-db")
def dump_db_command():
    """Dump the contents of the database"""
    conn = get_db_conn()
    cur = conn.cursor()
    # Get a list of tables
    tables = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

    # Now list each table
    for row in tables:
        table_name = row["name"]
        click.echo(f"Table: {table_name}")
        # Note we can't prepare the table name in the statement below
        rows = cur.execute(f"SELECT * FROM {table_name}").fetchall()
        if not rows:
            click.echo("Database is empty")
        else:
            header = rows[0].keys()
            click.echo(tabulate.tabulate(rows, header))
        print("")


@click.command("wipe-db")
def wipe_db_command():
    """Delete the database file. Note that we have to guess where the 'instance' is"""
    dbfile_path = join(current_app.instance_path, DBFILE_NAME)
    try:
        os.unlink(dbfile_path)
    except FileNotFoundError:
        pass


def init_app(app):
    """Initialize"""
    # always call close_db when connection is finished.
    app.teardown_appcontext(close_db)

    # Register CLI commands
    app.cli.add_command(init_db_command)
    app.cli.add_command(dump_db_command)
    app.cli.add_command(wipe_db_command)
