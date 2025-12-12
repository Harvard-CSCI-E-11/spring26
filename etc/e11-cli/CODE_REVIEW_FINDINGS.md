# Code Review Findings - E11 System

## Summary
This document contains findings from a comprehensive review of the e11 system, including the e11 module, command behavior with E11_STAFF, and AWS lambda functions.

---

## Critical Issues

### 1. Grade Key Pattern Issues (CRITICAL BUGS)
**Location**: `e11/e11_common.py`

**Issue 1a - Pattern Definition Bug**: The pattern definition on line 84 is incorrect:
```python
SK_GRADE_PATTERN = "{A.SK_GRADE_PREFIX}#{lab}#{now}"
```

When `.format(lab=lab, now=now)` is called on line 211, Python will try to replace `{A.SK_GRADE_PREFIX}` as a format key, but this is invalid (contains a dot) and will raise a `KeyError`. The pattern should be:
```python
SK_GRADE_PATTERN = f"{A.SK_GRADE_PREFIX}#{{lab}}#{{now}}"
```
or:
```python
SK_GRADE_PATTERN = A.SK_GRADE_PREFIX + "#{lab}#{now}"
```

**Issue 1b - Query Pattern Mismatch**: Even if the pattern worked, there's a mismatch:
- **Expected format** (per comment in `lambda-home/src/home_app/home.py:569`): `"grade#lab2#time"` (single hash)
- **Query pattern** (line 240): Uses `f'grade##{lab}'` which looks for `grade##lab1` (double hash)

**Impact**: 
- If Issue 1a exists, `add_grade()` will crash with KeyError when trying to store grades
- If Issue 1a is somehow working, then `get_grade()` will never find grades due to pattern mismatch

**Fix for Issue 1a**: Change line 84 to:
```python
SK_GRADE_PATTERN = A.SK_GRADE_PREFIX + "#{lab}#{now}"
```

**Fix for Issue 1b**: Change line 240 from:
```python
Key('sk').begins_with(f'grade##{lab}')
```
to:
```python
Key('sk').begins_with(f'grade#{lab}#')
```

**Also affects**: `e11/staff.py` lines 116 and 143 have the same query pattern issue.

---

## Typos

### 2. Typo in Leaderboard Flask App
**Location**: `lambda-leaderboard/src/leaderboard_app/flask_app.py:2`

**Issue**: 
- "Leaerboard" should be "Leaderboard"
- "Fask" should be "Flask"

**Fix**: 
```python
"""
Leaderboard Flask Application (src/app.py).
"""
```

### 3. Typo in Comment
**Location**: `e11/e11_common.py:223`

**Issue**: "user the users table" should be "use the users table"

**Fix**:
```python
def queryscan_table(what, kwargs):
    """use the users table and return the items"""
```

### 4. Typo in Comment
**Location**: `lambda-home/src/home_app/home.py:866`

**Issue**: "Unhandled innder exception" should be "Unhandled inner exception"

**Fix**:
```python
LOGGER.exception("Unhandled inner exception. ef=%s", ef)
```

---

## Style Issues

### 5. Inconsistent Spacing in Function Calls
**Location**: Multiple files

**Issue**: Inconsistent spacing around operators and in function calls:
- `e11/staff.py:19`: `dynamodb_client,dynamodb_resource,A,create_new_user` (no spaces after commas)
- `e11/main.py:23`: Similar issues

**Recommendation**: Use consistent spacing: `dynamodb_client, dynamodb_resource, A, create_new_user`

### 6. Inconsistent String Formatting
**Location**: Multiple files

**Issue**: Mix of f-strings and `.format()`:
- `e11/e11_common.py:84`: Uses `.format()` in pattern definition
- Most other places use f-strings

**Recommendation**: Standardize on f-strings for consistency (though pattern definitions may need `.format()` for delayed evaluation).

### 7. Inconsistent Error Message Formatting
**Location**: Multiple files

**Issue**: Some error messages use f-strings, others use format strings:
- `e11/main.py:201`: `f"ERROR: {at} not in configuration file."`
- `e11/main.py:240`: `f"\n{errors} error{'s' if errors!=1 else ''} in configuration file."`

**Recommendation**: Standardize error message format across the codebase.

### 8. Missing Space in Comment
**Location**: `lambda-leaderboard/src/leaderboard_app/flask_app.py:269`

**Issue**: `# pylint disable=missing-function-docstring` should have a colon:
```python
# pylint: disable=missing-function-docstring
```

---

## Code Quality Issues

### 9. Inconsistent Error Handling
**Location**: `e11/main.py:258-262`

**Issue**: The `TimeoutError` exception handling in `do_register()` catches `TimeoutError` but the code uses `requests.post()` which raises `requests.exceptions.Timeout`, not `TimeoutError`.

**Fix**: Should catch `requests.exceptions.Timeout`:
```python
except requests.exceptions.Timeout:
```

### 10. Inconsistent Return Type Handling
**Location**: `e11/e11_common.py:235-248`

**Issue**: `get_grade()` returns `int(score)` but `score` comes from `max()` on string values. The conversion should happen earlier.

**Current code**:
```python
score = max( (item['score'] for item in items) )
return int(score)
```

**Better**:
```python
scores = [int(item['score']) for item in items]
return max(scores) if scores else 0
```

### 11. Potential KeyError
**Location**: `e11/e11_common.py:245`

**Issue**: If `item['score']` doesn't exist, this will raise KeyError. Should use `.get()`:
```python
score = max( (int(item.get('score', 0)) for item in items) )
```

### 12. Inconsistent Variable Naming
**Location**: Multiple files

**Issue**: Mix of `instanceId` and `instance_id`:
- `e11/main.py:223, 224, 454`: Uses `instanceId` (camelCase)
- `e11/e11_common.py:87`: Uses `USER_ID` (snake_case)

**Recommendation**: Standardize on snake_case for Python code.

### 13. Magic String in Error Response
**Location**: `lambda-home/src/home_app/home.py:854`

**Issue**: Returns status code 302 (redirect) for an error, which is incorrect. Should be 403 or 400:
```python
return resp_json(403, {"error": f"Email not registered {e}"})
```

### 14. Incomplete Error Handling
**Location**: `e11/main.py:76`

**Issue**: String comparison for version numbers:
```python
if __version__.split() < data['version'].split():
```

This compares lists lexicographically, which may not work correctly for version numbers like "0.2.2" vs "0.10.0". Should use proper version comparison.

### 15. Missing Error Handling
**Location**: `e11/main.py:70`

**Issue**: No error handling for `requests.post()` - if the request fails, `r.json()` will raise an exception:
```python
r = requests.post(ep, json={'action':'version'},timeout=5)
data = r.json()  # Will raise if r.ok is False
```

Should check `r.ok` first or use `r.raise_for_status()`.

---

## Consistency Issues

### 16. Inconsistent Import Style
**Location**: Multiple files

**Issue**: Some files use absolute imports, others use relative. The codebase should be consistent.

**Example**:
- `e11/main.py:22`: `from . import staff`
- `e11/staff.py:19`: `from .e11_common import ...`

**Note**: User preference is for absolute imports (per memory).

### 17. Inconsistent Logging
**Location**: Multiple files

**Issue**: Some places use `LOGGER`, others use `logger`, and some use `app.logger`:
- `e11/e11core/grader.py:23`: `LOGGER = get_logger("grader")`
- `e11/main.py:39`: `logger = get_logger()`
- `lambda-leaderboard/src/leaderboard_app/flask_app.py:41`: `app.logger.setLevel(logging.DEBUG)`

**Recommendation**: Standardize on `LOGGER` for module-level loggers.

### 18. Inconsistent Time Handling
**Location**: Multiple files

**Issue**: Mix of `time.time()` and `datetime.datetime.now()`:
- `e11/e11_common.py:151`: `int(time.time())`
- `e11/e11_common.py:208`: `datetime.datetime.now().isoformat()`

**Recommendation**: Use `time.time()` for timestamps (integers) and `datetime` for ISO strings, but be consistent about when to use each.

### 19. Inconsistent Table Name References
**Location**: Multiple files

**Issue**: Hardcoded table names vs environment variables:
- `e11/staff.py:38`: `dynamodb_resource.Table('e11-users')` (hardcoded)
- `e11/e11_common.py:42`: `USERS_TABLE_NAME = os.environ.get("USERS_TABLE_NAME","e11-users")` (env var with default)

**Recommendation**: Always use the constant from `e11_common.py`.

---

## Documentation Issues

### 20. Incomplete Docstring
**Location**: `e11/e11_common.py:185`

**Issue**: `add_user_log()` docstring doesn't document all parameters:
```python
def add_user_log(event, user_id, message, **extra):
    """
    :param user_id: user_id
    :param message: Message to add to log
    """
```

Should document `event` and `**extra` parameters.

### 21. Outdated Comment
**Location**: `lambda-home/src/home_app/common.py:19`

**Issue**: Comment says "Don't know why this is necessary" - should either explain or remove if no longer needed.

---

## Minor Issues

### 22. Unused Variable
**Location**: `e11/main.py:312`

**Issue**: `result` is assigned but `r.json()` is called again on line 314:
```python
result = r.json()
if not r.ok:
    ...
try:
    print_summary(result['summary'], ...)
```

This is fine, but could be cleaner.

### 23. Redundant Check
**Location**: `e11/staff.py:236`

**Issue**: `if not user:` check after `get_user_from_email()` which raises `EmailNotRegistered` if user doesn't exist, so the check is unreachable.

### 24. Inconsistent Quote Style
**Location**: Multiple files

**Issue**: Mix of single and double quotes. Should standardize (PEP 8 recommends consistency within a file).

---

## Recommendations

1. **Fix the critical grade key pattern bug immediately** - this affects grade retrieval
2. **Standardize error handling** - use consistent exception types and error response formats
3. **Add type hints** - many functions lack type hints which would improve code quality
4. **Add unit tests** - especially for the grade retrieval functions
5. **Document E11_STAFF behavior** - add clear documentation about how staff mode works
6. **Standardize naming conventions** - use snake_case consistently for Python code
7. **Add input validation** - many functions don't validate inputs before use

---

## Files Requiring Attention

1. `e11/e11_common.py` - Critical bug in grade key pattern
2. `e11/staff.py` - Same grade key pattern bug, inconsistent table name usage
3. `lambda-leaderboard/src/leaderboard_app/flask_app.py` - Typos in docstring
4. `e11/main.py` - Error handling issues, version comparison bug
5. `lambda-home/src/home_app/home.py` - Typo, incorrect status code

---

## E11_STAFF Behavior Review

The E11_STAFF environment variable enables staff-only commands when set to a truthy value (Y, T, or 1). This is implemented in:
- `e11/staff.py:22`: `enabled()` function checks the environment variable
- `e11/main.py:476-477`: Staff parsers are added conditionally
- `e11/main.py:490`: Staff commands bypass EC2 check

**Findings**:
- Implementation is clean and straightforward
- No issues found with the E11_STAFF behavior
- Staff commands properly isolated from regular user commands

---

## Lambda Functions Review

### lambda-home
- Well-structured with clear separation of concerns
- Good error handling overall
- Minor typo and status code issue noted above

### lambda-leaderboard  
- Typo in module docstring
- Missing pylint colon in comment
- Otherwise well-structured

### lambda-users-db
- Simple CloudFormation template
- No code issues found

---

## Next Steps

1. Fix critical grade key pattern bug
2. Fix typos
3. Address error handling inconsistencies
4. Standardize code style
5. Add missing documentation

