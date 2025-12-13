"""
conftest.py - additions for pytest for this and descendent directories.
"""

import os
import pytest
import boto3
from botocore.exceptions import ClientError

# pylint: disable=missing-function-docstring

# Configure boto3 to use local DynamoDB endpoint
DYNAMODB_LOCAL_ENDPOINT = os.environ.get('AWS_ENDPOINT_URL_DYNAMODB', 'http://localhost:8010/')

def pytest_configure(config):
    """Configure pytest to use local DynamoDB"""
    # Set environment variables if not already set
    if 'AWS_ENDPOINT_URL_DYNAMODB' not in os.environ:
        os.environ['AWS_ENDPOINT_URL_DYNAMODB'] = DYNAMODB_LOCAL_ENDPOINT
    if 'AWS_ACCESS_KEY_ID' not in os.environ:
        os.environ['AWS_ACCESS_KEY_ID'] = 'minioadmin'
    if 'AWS_SECRET_ACCESS_KEY' not in os.environ:
        os.environ['AWS_SECRET_ACCESS_KEY'] = 'minioadmin'
    if 'AWS_DEFAULT_REGION' not in os.environ:
        os.environ['AWS_DEFAULT_REGION'] = 'us-east-1'

@pytest.fixture(scope="session")
def dynamodb_local():
    """Ensure local DynamoDB is running and table exists"""
    # Check if DynamoDB Local is running
    import requests
    try:
        requests.get(DYNAMODB_LOCAL_ENDPOINT, timeout=1)
    except requests.exceptions.RequestException:
        pytest.skip("DynamoDB Local is not running. Run 'make start_local_dynamodb' first.")
    
    # Create table if it doesn't exist
    dynamodb = boto3.resource('dynamodb', endpoint_url=DYNAMODB_LOCAL_ENDPOINT, region_name='us-east-1')
    table_name = 'Leaderboard'
    
    try:
        table = dynamodb.Table(table_name)
        table.load()  # Check if table exists
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            # Create the table
            table = dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {
                        'AttributeName': 'name',
                        'KeyType': 'HASH'
                    }
                ],
                AttributeDefinitions=[
                    {
                        'AttributeName': 'name',
                        'AttributeType': 'S'
                    }
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            # Wait for table to be created
            table.wait_until_exists()
    
    yield dynamodb
    
    # Cleanup: delete all items from the table
    table = dynamodb.Table(table_name)
    scan = table.scan()
    with table.batch_writer() as batch:
        for item in scan['Items']:
            batch.delete_item(Key={'name': item['name']})

def pytest_runtest_setup(item):
    if "docker" in item.keywords and os.getenv("IS_DOCKER") != "true":
        pytest.skip("Skipping Docker-only test because IS_DOCKER is not set.")


# run pytest -m 'docker' to run docker-specific tests
def pytest_collection_modifyitems(config, items):
    if not config.getoption("-m") or "docker" not in config.getoption("-m"):
        skip_docker = pytest.mark.skip(reason="Skipping Docker-only tests")
        for item in items:
            if "docker" in item.keywords:
                item.add_marker(skip_docker)
