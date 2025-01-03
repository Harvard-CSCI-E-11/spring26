"""
Test the leaderboard.
"""

import pytest
from flask import render_template
from leaderboard_app import app

@pytest.fixture
def app_context():
    """generate an app context for testing"""
    with app.app_context():
        yield

def test_template_rendering(app_context):
    """Test the rendering engine"""
    rendered = render_template("demo_client.html", var="value")
    assert "<title>Leaderboard Client</title>" in rendered


def test_client_request(app_context):
    """Test the leaderboard function"""
    client = app.test_client()
    response = client.get('/api/leaderboard')
    assert response.status_code == 200
