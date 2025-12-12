"""
Lambda handler for AWS API Gateway
"""

from apig_wsgi import make_lambda_handler
from . import flask_app
lambda_handler = make_lambda_handler(flask_app.app)
