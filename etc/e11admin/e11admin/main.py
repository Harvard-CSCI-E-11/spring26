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
    for name in ['Leaderboard','e11-users','home-app-prod-sessions','home-app-stage-sessions']:
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
    pusers = [ (user.get('preferred_name','n/a'),
                user.get('email','n/a'),
                time.asctime(time.localtime(int(user.get('user_registered',0)))),
                user.get('public_ip','n/a/')
                )
              for user in users]
    pusers.sort()
    print(tabulate(pusers,headers=['name','email','registered','public_ip']))

def dump_users_table(args):
    items = []
    response = users_table.scan()
    items.extend(response['Items'])

    # Continue scanning if the table is larger than 1MB (pagination)
    while 'LastEvaluatedKey' in response:
        response = users_table.scan( FilterExpression=filter_expr,
                                     ExclusiveStartKey=response['LastEvaluatedKey'] )
        items.extend(response['Items'])

    print(f"Scan complete. Found {len(items)} items")
    printable = {}
    for item in items:
        user_id = item['user_id']
        if user_id not in printable:
            printable[user_id] = user_id[0:3] + " " + item.get('preferred_name','')[0:15]
        print(printable[user_id],item['sk'],item.get('message','')[0:40])
        if item['sk']=='#':
            print(item)
        if args.dump:
            print(item)

def main():
    parser = argparse.ArgumentParser(prog='e11admin', description='E11 admin program', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--dump", help='Dump all ', action='store_true')
    args = parser.parse_args()
    validate_dynamodb()
    show_registered_users()
    dump_users_table(args)


if __name__=="__main__":
    main()
