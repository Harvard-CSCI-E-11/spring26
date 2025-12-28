"""
lab7 tester - just make sure they hit the leaderboard
"""
# pylint: disable=duplicate-code

import os
import functools

from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

from e11.e11_common import get_user_from_email,queryscan_table,users_table, A
from e11.e11core.utils import get_logger
from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
logger = get_logger()

MAGIC = 'magic'

@functools.lru_cache(maxsize=10)
def get_leaderboard_log( tr  ):
    if not os.getenv("LEADERBOARD_TABLE_NAME"):
        raise TestFail("This test only runs from the course dashboard")

    user =  get_user_from_email(tr.ctx.email)
    kwargs = {'KeyConditionExpression' : (
	Key(A.USER_ID).eq(user.user_id) &
        Key(A.SK).begins_with(A.SK_LEADERBOARD_LOG_PREFIX)
    )}
    try:
        return queryscan_table(users_table.query, kwargs)
    except ClientError as e:
        raise TestFail(str(e)) from e

@timeout(5)
def test_leaderboard( tr:TestRunner ):
    if not os.getenv("LEADERBOARD_TABLE_NAME"):
        raise TestFail("This test only runs from the course dashboard")

    items = get_leaderboard_log( tr )
    if not items:
        raise TestFail("No messages on leaderboard.")
    try:
        return f"User registered with leaderboard (count={len(items)})"
    except ClientError as e:
        raise TestFail(str(e)) from e

@timeout(5)
def test_has_magic( tr:TestRunner ):
    if not os.getenv("LEADERBOARD_TABLE_NAME"):
        raise TestFail("This test only runs from the course dashboard")

    items = get_leaderboard_log( tr )
    has_magic = any( ( MAGIC.lower() in item.get('user_agent','').lower() for item in items ) )
    if has_magic:
        return "user_agent string included the word 'magic'"
    try:
        raise TestFail("No leaderboard message contained the word 'magic'")
    except ClientError as e:
        raise TestFail(str(e)) from e
