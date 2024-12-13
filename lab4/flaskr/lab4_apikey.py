"""
Web application for Amazon rekognition demo.
Also maintains the API_KEY database.
"""

import base64
import os
import os.path
from hashlib import pbkdf2_hmac

import tabulate
import click
from .db import get_db

# APIKEY Management Tools

ALGORITHM  = 'sha256'
ITERATIONS = 10000
DKLEN      = 64

def new_apikey():
    """Create a new API key, insert the hashed key in the database, and return the key"""
    api_key        = base64.b64encode(os.urandom(16)).decode('utf-8')
    api_secret_key = base64.b64encode(os.urandom(16)).decode('utf-8')
    salt           = os.urandom(8)
    api_secret_key_hash = pbkdf2_hmac(ALGORITHM, api_secret_key, salt, ITERATIONS, dklen=DKLEN)
    to_store = f'pbkdf2:{ALGORITHM}:{ITERATIONS}:{salt.hex()}:{api_secret_key_hash.hex()}'
    db  = get_db()
    cur = db.cursor()
    cur.execute("insert into api_keys (api_key,api_secret_key_hash) values (?,?)",
                (api_key, to_store))
    db.commit()
    return (api_key,api_secret_key)

def validate_api_key(api_key, api_secret_key):
    """Given an api_key and the secret key:
    1. Pull the api_secret_key's hash and hash parameters from the database.
    2. Hash the provided api_secret_key.
    3. See if the two hashes match.
    """
    db = get_db()
    cur = db.cursor()

    # Get the hashed password and stored salt and iteration count
    stored = cur.execute("select api_secret_key_hash from api_keys where api_key=? ",
                         (api_key,)).fetchall()
    if len(stored)!=1:
        return False
    # pylint: disable=line-too-long
    (check,stored_algorithm,stored_iterations_dec,stored_salt_hex,stored_hash_hex) = stored.split(':')
    assert check=='pbkdf2'
    stored_iterations = int(stored_iterations_dec) # turn to integer
    stored_salt      = bytes.fromhex(stored_salt_hex)

    # Generate a hash from the provided
    hashed = pbkdf2_hmac(stored_algorithm, api_secret_key, stored_salt, stored_iterations, dklen=DKLEN)

    return hashed.hex() == stored_hash_hex


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


# Init code
def init_app(app):
    """Init the app"""
    app.cli.add_command(new_apikey_command)
    app.cli.add_command(dump_db_command)
