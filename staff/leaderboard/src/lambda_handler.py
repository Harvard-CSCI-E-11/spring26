"""
Lambda handler for AWS API Gateway
"""

from apig_wsgi import make_lambda_handler
import leaderboard_app
lambda_app = make_lambda_handler(leaderboard_app.app)
