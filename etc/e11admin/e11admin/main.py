"""
e11admin main program
"""

import time
import argparse

import boto3
from boto3.dynamodb.conditions import Key,Attr
from tabulate import tabulate

dynamodb_client = boto3.client('dynamodb')
dynamodb = boto3.resource('dynamodb')
users_table = dynamodb.Table('e11-users')

def validate_dynamodb():
    r = dynamodb_client.list_tables()
    print("DynamoDB Tables:")
    for table_name in r['TableNames']:
        print(f"- {table_name}")
    for name in ['Leaderboard','e11-users','home-app-sessions']:
        assert name in r['TableNames']

def get_all_sk(sk, projection=None):
    """Search the users table and returns all of the recoreds with a particular sk.
    Currently this requires a scan. We need to modify the schema to allow us to do this efficiently with a query.
    """
    all_users = []
    # Use a FilterExpression to find items where 'sk' equals 'USER'
    filter_expr = Attr('sk').eq(sk)

    # Start the scan
    response = users_table.scan( FilterExpression=filter_expr )
    all_users.extend(response['Items'])
    calls = 1

    while 'LastEvaluatedKey' in response:
        response = users_table.scan( FilterExpression=filter_expr,
                                     ExclusiveStartKey=response['LastEvaluatedKey'] )
        all_users.extend(response['Items'])
        calls += 1

    print(f"Scan complete. Found {len(all_users)} users. calls={calls}")
    return all_users

def show_registered_users():
    users = get_all_sk('#',projection='user_registered,email,claims')
    pusers = [ (user['claims']['name'], user['email'], time.asctime(time.localtime(int(user['user_registered']))))
              for user in users]
    pusers.sort()
    print(tabulate(pusers,headers=['name','email','registered']))

def dump_users_table():
    items = []
    response = users_table.scan()
    items.extend(response['Items'])

    # Continue scanning if the table is larger than 1MB (pagination)
    while 'LastEvaluatedKey' in response:
        response = users_table.scan( FilterExpression=filter_expr,
                                     ExclusiveStartKey=response['LastEvaluatedKey'] )
        items.extend(response['Items'])

    print(f"Scan complete. Found {len(items)} items")
    for item in items:
        #print(item)
        print(item['sk'])

def main():
    parser = argparse.ArgumentParser(prog='e11admin', description='E11 admin program')
    args = parser.parse_args()
    validate_dynamodb()
    show_registered_users()
    #dump_users_table()


if __name__=="__main__":
    main()
