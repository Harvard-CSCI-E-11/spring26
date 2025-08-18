"""
Lambda handler for AWS API Gateway
"""

from apig_wsgi import make_lambda_handler
from flask_app import app
lambda_app = make_lambda_handler(app)
