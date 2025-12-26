"""
lab7 tester - just make sure they hit the leaderboard
"""
# pylint: disable=duplicate-code

import functools

from boto3.dynamodb.conditions import Key

from e11.e11_common import get_user_from_email,queryscan_table,users_table, A
from e11.e11core.utils import get_logger
from e11.e11core.decorators import timeout
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail
logger = get_logger()

MAGIC = 'magic'

@functools.lru_cache(maxsize=10)
def get_leaderboard_log( tr  ):
    user =  get_user_from_email(tr.ctx.email)
    kwargs:dict = {'KeyConditionExpression' : (
	Key(A.USER_ID).eq(user.user_id) &
        Key(A.SK).begins_with(A.SK_LEADERBOARD_LOG_PREFIX)
    )}
    return queryscan_table(users_table.query, kwargs)

@timeout(5)
def test_leaderboard( tr:TestRunner ):
    items = get_leaderboard_log( tr )
    if not items:
        raise TestFail("No messages on leaderboard.")
    return f"User registered with leaderboard (count={len(items)})"

@timeout(5)
def test_has_magic( tr:TestRunner ):
    items = get_leaderboard_log( tr )
    has_magic = any( ( MAGIC.lower() in item.get('user_agent','').lower() for item in items ) )
    if has_magic:
        return "user_agent string included the word 'magic'"
    raise TestFail("No leaderboard message contained the word 'magic'")
