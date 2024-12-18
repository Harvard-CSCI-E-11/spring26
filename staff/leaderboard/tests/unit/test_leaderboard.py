import pytest
from leaderboard_app import app
from flask import render_template

@pytest.fixture
def app_context():
    with app.app_context():
        yield

def test_template_rendering(app_context):
    rendered = render_template("demo_client.html", var="value")
    assert "<title>Leaderboard Client</title>" in rendered


def test_client_request(app_context):
    client = app.test_client()
    response = client.get('/api/leaderboard')
    assert response.status_code == 200
