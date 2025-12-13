"""
Test the leaderboard.
"""

import logging
import pytest
from flask import render_template

from leaderboard_app.flask_app import app


@pytest.fixture
def app_context():
    """generate an app context for testing"""
    with app.app_context():
        yield

def test_template_rendering(app_context):
    """Test the rendering engine"""
    rendered = render_template("demo_client.html", var="value")
    assert "<title>Leaderboard Client</title>" in rendered


def test_client_request(app_context, dynamodb_local):
    """Test the leaderboard function"""
    client = app.test_client()
    r1 = client.get('/api/register')
    assert r1.status_code == 200
    myname = r1.json['name']
    logging.info("name: %s", myname)

    r2 = client.post('/api/update', data=r1.json)
    assert r2.status_code == 200
    leaderboard = r2.json['leaderboard']
    logging.info("Entries in leaderboard: %s",len(leaderboard))

    me = [leader for leader in leaderboard if leader['name'] == myname]
    logging.info("me: %s",me)
    if len(me)==0:
        logging.error("%s not in the leaderboard.",myname)
        for leader in leaderboard:
            logging.error(leader)
        raise RuntimeError("not in leaderboard")
