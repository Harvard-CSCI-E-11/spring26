"""
Web application for Amazon rekognition demo.
Also maintains the API_KEY database.
"""

import base64
import time
import os
import os.path
import tabulate
import logging
from os.path import join, basename, abspath, dirname
import sqlite3

import click
import pbkdf2
from flask import current_app, g
from .db import get_db

DB_FILE = join(os.getenv("HOME"), "lab4.db")
SCHEMA_FILE = join(dirname(__file__), "schema.sql")

# If the database does not exist, create it with the correct schema

def new_apikey():
    """Create a new API key, insert the hashed key in the database, and return the key"""
    api_key        = base64.b64encode(os.urandom(16)).decode('utf-8')
    api_secret_key = base64.b64encode(os.urandom(16)).decode('utf-8')
    api_secret_key_hash = pbkdf2.crypt(api_secret_key)
    db = get_db()
    cur = db.cursor()
    cur.execute("insert into api_keys (api_key,api_secret_key_hash) values (?,?)",
                (api_key, api_secret_key_hash))
    db.commit()
    return (api_key,api_secret_key)

@click.command("new-apikey")
def new_apikey_command():
    """Create a new API key and print it"""
    (api_key,api_secret_key) = new_apikey()
    click.echo(f"API_KEY: {api_key}")
    click.echo(f"API_SECRET_KEY: {api_secret_key}")


@click.command("dump-db")
def dump_db_command():
    """Dump the contents of the database"""
    db = get_db()
    cur = db.cursor()
    rows = cur.execute("select api_key, api_secret_key_hash, created,"
                       "last_used, remaining from api_keys").fetchall()
    if not rows:
        click.echo("Database is empty")
        return
    header = rows[0].keys()
    click.echo(tabulate.tabulate(rows,header))

def init_lab4_app(app):
    app.cli.add_command(new_apikey_command)
    app.cli.add_command(dump_db_command)
