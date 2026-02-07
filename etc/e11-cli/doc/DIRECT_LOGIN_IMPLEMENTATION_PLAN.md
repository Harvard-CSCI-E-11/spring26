# Direct Login Implementation Plan

## Overview

Implement a special login flow for users whose accounts were created via `e11 register-email` (staff account creation) who have email and course_key but no OIDC claims. This allows them to log in via a URL with a base64-encoded token containing user_id and course_key, bypassing the OIDC flow.

**Terminology Note:**
- **Account Registration** (`e11 register-email`): Staff creates a student account in the database (user record with email + course_key, no claims)
- **Instance Registration** (`e11 register`): Student registers their VM instance (links VM to account, sets public_ip, preferred_name, etc.)

## Requirements

1. New route: `/login-direct?token=<base64(user_id:course_key)>`
2. Decode token to extract user_id and course_key
3. Look up user by user_id
4. Validate course_key matches
5. Check that user has no claims (or claims is None)
6. If user has claims, redirect to `/login`
7. Create a session with minimal claims (for compatibility)
8. Set cookie and redirect to dashboard
9. Modify `e11 register-email` (staff account creation command) to generate and display the login URL
10. Add comprehensive test coverage using DynamoDB Local

---

## Implementation Steps

### Step 1: Add Helper Function to Get User by user_id

**File:** `lambda-home/src/home_app/e11_common.py` (or `e11/e11_common.py` - need to check where to add)

**Function:** `get_user_from_user_id(user_id) -> User`

**Rationale:** We need to look up users by user_id instead of email for the token-based login.

**Code:**
```python
def get_user_from_user_id(user_id: str) -> User:
    """Get user record by user_id."""
    logger = get_logger()
    logger.debug("get_user_from_user_id: looking for user_id=%s", user_id)
    resp = users_table.get_item(
        Key={A.USER_ID: user_id, A.SK: A.SK_USER}
    )
    if "Item" not in resp:
        raise EmailNotRegistered(f"User {user_id} not found")
    item = resp["Item"]
    logger.debug("get_user_from_user_id - item=%s", item)
    return User(**convert_dynamodb_item(item))
```

**Note:** This function should be added to `e11/e11_common.py` since it's shared code used by both CLI and Lambda.

---

### Step 2: Add Direct Login Handler Function

**File:** `lambda-home/src/home_app/home.py`

**Function:** `do_login_direct(event)`

**Logic:**
1. Extract `token` from query string parameters
2. Validate token is present
3. Decode base64 token
4. Split on `:` to extract user_id and course_key
5. Use `get_user_from_user_id(user_id)` to fetch user from DynamoDB Local
6. Verify `user.course_key == course_key`
7. If user has claims → redirect to `/login`
8. Create minimal claims dict: `{A.EMAIL: user.email}`
9. Call `new_session(event, claims=minimal_claims)`
10. Create session cookie using `make_cookie()`
11. Redirect to `/dashboard` with cookie

**Error handling:**
- Missing token → return error page
- Invalid base64 → return error page
- User not found → return error with message "Course key mismatch for email {email} or email is not registered."
- Invalid course_key → return error with message "Course key mismatch for email {email} or email is not registered."
- User already has claims → redirect to `/login`

**Code structure:**
```python
import base64
import binascii

def do_login_direct(event):
    """/login-direct?token=<base64(user_id:course_key)> - Direct login for users without OIDC claims"""
    qs = event.get("queryStringParameters") or {}
    token = qs.get("token")
    
    if not token:
        return resp_text(HTTP_BAD_REQUEST, "Missing token parameter")
    
    try:
        # Decode base64 token
        try:
            decoded = base64.urlsafe_b64decode(token + '==').decode('utf-8')
            user_id, course_key = decoded.split(':', 1)
        except (ValueError, UnicodeDecodeError, binascii.Error) as e:
            LOGGER.warning("Invalid token format: %s", e)
            return resp_text(HTTP_BAD_REQUEST, "Invalid token format")
        
        # Get user by user_id
        user = get_user_from_user_id(user_id)
        
        # Verify course_key matches
        if user.course_key != course_key:
            email_display = user.email or "unknown"
            return resp_text(
                HTTP_FORBIDDEN, 
                f"Course key mismatch for email {email_display} or email is not registered."
            )
        
        # If user has claims, redirect to regular login
        if user.claims is not None:
            return redirect("/login")
        
        # Create minimal claims for session (for compatibility with existing code)
        minimal_claims = {A.EMAIL: user.email}
        
        # Create session
        ses = new_session(event, claims=minimal_claims)
        
        # Set cookie and redirect
        sid_cookie = make_cookie(
            COOKIE_NAME, ses.sid, max_age=SESSION_TTL_SECS, domain=get_cookie_domain(event)
        )
        LOGGER.info("Direct login: created session for email=%s", user.email)
        add_user_log(event, user.user_id, f"Session {ses.sid} created (direct_login)")
        return redirect("/dashboard", cookies=[sid_cookie])
        
    except EmailNotRegistered:
        return resp_text(
            HTTP_FORBIDDEN, 
            "Course key mismatch for email unknown or email is not registered."
        )
    except Exception as e:
        LOGGER.exception("Error in do_login_direct: %s", e)
        return resp_text(HTTP_INTERNAL_ERROR, "Internal server error")
```

---

### Step 3: Add Route in lambda_handler

**File:** `lambda-home/src/home_app/home.py`

**Location:** In the `match (method, path):` statement, add before the `/` route:

```python
case ("GET", "/login-direct"):
    return do_login_direct(event)
```

**Placement:** Add after `/logout` and before `/` to ensure it's caught before the catch-all.

---

### Step 4: Add URL Generation Function

**File:** `e11/e11_common.py` (or helper in staff.py)

**Function:** `generate_direct_login_url(user_id: str, course_key: str, domain: str = None) -> str`

**Code:**
```python
import base64
from e11.e11core.constants import COURSE_DOMAIN

def generate_direct_login_url(user_id: str, course_key: str, domain: str = None) -> str:
    """Generate direct login URL with base64-encoded token."""
    if domain is None:
        domain = COURSE_DOMAIN
    
    # Create token: user_id:course_key
    token_data = f"{user_id}:{course_key}"
    # Base64 encode (URL-safe, no padding needed but add == for safety)
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')
    
    return f"https://{domain}/login-direct?token={token}"
```

---

### Step 5: Modify register-email Command (Staff Account Creation)

**File:** `e11/staff.py`

**Function:** `do_register_email(args)`

**Purpose:** Staff command to create a student account (not to be confused with `e11 register` which registers a VM instance)

**Changes:**
- After creating user account, generate direct login URL
- Print the URL along with course_key

**Updated code:**
```python
def do_register_email(args):
    email = args.email
    # See if the email exists
    response = dynamodb_resource.Table('e11-users').scan(FilterExpression = Attr('email').eq(email))
    if response.get('Items'):
        user = response.get('Items')[0]
        course_key = user[A.COURSE_KEY]
        user_id = user[A.USER_ID]
        login_url = generate_direct_login_url(user_id, course_key)
        print(f"User {email} already exists.\ncourse_key={course_key}\nLogin URL: {login_url}")
        sys.exit(0)
    
    user = create_new_user(email)
    course_key = user[A.COURSE_KEY]
    user_id = user[A.USER_ID]
    login_url = generate_direct_login_url(user_id, course_key)
    print(f"Registered {email}\ncourse_key={course_key}\nLogin URL: {login_url}")
```

**Note:** Need to import `generate_direct_login_url` in staff.py.

---

### Step 6: Update new_session() Logging

**File:** `lambda-home/src/home_app/sessions.py`

**Changes:**
- No function signature changes needed (using minimal claims approach)
- Update log message to include "(direct_login)" when appropriate

**Note:** Actually, we can't easily detect if it's direct login in `new_session()` since we're using minimal claims. The log message with "(direct_login)" should be added in `do_login_direct()` after calling `new_session()`, as shown in Step 2.

---

### Step 7: Create Test File

**File:** `lambda-home/tests/test_direct_login.py`

**Test Cases:**

1. **test_direct_login_success** - Happy path
   - Create user via `create_new_user(email)` (no claims)
   - Generate token: base64(user_id:course_key)
   - Call `/login-direct?token=...`
   - Verify session created in DynamoDB Local
   - Verify cookie set and redirect to /dashboard
   - Verify session has minimal claims (just email)

2. **test_direct_login_missing_token** - Missing token
   - Call `/login-direct` without token
   - Verify 400 error returned

3. **test_direct_login_invalid_token_format** - Invalid base64
   - Call `/login-direct?token=not-base64`
   - Verify 400 error returned

4. **test_direct_login_invalid_user_id** - User doesn't exist
   - Generate token with non-existent user_id
   - Verify 403 error with message "Course key mismatch for email unknown or email is not registered."

5. **test_direct_login_invalid_course_key** - Wrong course_key
   - Create user, generate token with wrong course_key
   - Call `/login-direct?token=...`
   - Verify 403 error with message containing user email

6. **test_direct_login_user_has_claims** - User already has OIDC claims
   - Create user with claims: `create_new_user(email, claims={...})`
   - Generate valid token
   - Call `/login-direct?token=...`
   - Verify redirect to `/login`

7. **test_direct_login_session_created_in_db** - Verify DynamoDB integration
   - Create user
   - Call direct login
   - Query sessions table directly to verify session exists
   - Verify session.claims contains email
   - Verify session.email matches

8. **test_direct_login_can_access_dashboard** - End-to-end flow
   - Create user
   - Call direct login
   - Extract cookie from response
   - Make request to /dashboard with cookie
   - Verify dashboard loads successfully

9. **test_generate_direct_login_url** - URL generation
   - Test URL generation function
   - Verify token is valid base64
   - Verify URL format is correct

**Test fixture:**
```python
@pytest.fixture
def direct_login_user(fake_aws, dynamodb_local):
    """Create a test user WITHOUT claims for direct login testing (simulates staff account creation via register-email)"""
    from e11.e11_common import create_new_user, A
    import uuid
    
    test_email = f"direct-{uuid.uuid4().hex[:8]}@example.com"
    user = create_new_user(test_email)  # No claims - simulates staff account creation (register-email)
    return {
        "email": test_email,
        "course_key": user[A.COURSE_KEY],
        "user_id": user[A.USER_ID]
    }
```

**Test structure example:**
```python
def test_direct_login_success(fake_aws, dynamodb_local, direct_login_user):
    """Test successful direct login for user without claims"""
    from home_app.home import lambda_handler
    from e11.e11_common import generate_direct_login_url
    from test_utils import create_lambda_event
    import base64
    
    # Generate token
    token_data = f"{direct_login_user['user_id']}:{direct_login_user['course_key']}"
    token = base64.urlsafe_b64encode(token_data.encode('utf-8')).decode('utf-8').rstrip('=')
    
    # Create event
    event = create_lambda_event(
        "/login-direct",
        method="GET",
        qs={"token": token}
    )
    
    # Call handler
    response = lambda_handler(event, None)
    
    # Verify redirect to dashboard
    assert response["statusCode"] == HTTP_FOUND
    assert response["headers"]["location"] == "/dashboard"
    
    # Verify cookie is set
    cookies = response.get("cookies", [])
    assert any("AuthSid=" in c for c in cookies)
    
    # Verify session exists in DynamoDB Local
    from home_app.sessions import all_sessions_for_email
    sessions = all_sessions_for_email(direct_login_user["email"])
    assert len(sessions) == 1
    assert sessions[0]["email"] == direct_login_user["email"]
    # Session will have minimal claims with email
```

**Important:** All tests must use DynamoDB Local (via `fake_aws` and `dynamodb_local` fixtures). Do NOT mock DynamoDB operations.

---

## File Changes Summary

1. **e11/e11_common.py**
   - Add `get_user_from_user_id(user_id)` function
   - Add `generate_direct_login_url(user_id, course_key, domain)` function

2. **lambda-home/src/home_app/home.py**
   - Add `do_login_direct(event)` function
   - Add route case for `/login-direct` in `lambda_handler()`
   - Import base64 and get_user_from_user_id

3. **e11/staff.py**
   - Modify `do_register_email()` to generate and print login URL
   - Import `generate_direct_login_url`

4. **lambda-home/tests/test_direct_login.py** (NEW FILE)
   - Comprehensive test suite with 9+ test cases
   - All tests use DynamoDB Local, not mocks

---

## Testing Strategy

### Unit Tests
- Test `get_user_from_user_id()` function
- Test `generate_direct_login_url()` function
- Test `do_login_direct()` with various error cases

### Integration Tests  
- End-to-end flow: URL → token decode → session creation → cookie → dashboard access
- Verify DynamoDB Local integration
- Verify session persistence
- Test register-email command output

### Test Data Setup
- Use `create_new_user(email)` to create users without claims (simulates staff account creation via `register-email`)
- Use `create_new_user(email, claims={...})` to create users with claims (simulates OIDC login)
- Note: `register-email` creates accounts; `register` links VM instances to accounts (different operations)
- Use `get_user_from_user_id()` to verify user state
- Query sessions table directly to verify session creation

---

## Security Considerations

1. **Token Format:** Base64 encoding provides minimal obfuscation, not security
   - Acceptable for this use case (course_key acts as password)
   - Token contains user_id:course_key, both needed for login
   - Consider adding rate limiting if needed

2. **Session Security:** Sessions use UUID v4 (hard to guess)
   - Same security model as OIDC sessions

3. **Validation:** Always validate course_key matches before creating session
   - Prevents unauthorized access

4. **Claims Check:** Redirect to /login if user has claims
   - Prevents bypassing OIDC for users who should use it

---

## Edge Cases to Handle

1. User doesn't exist → 403 error with message about course key mismatch
2. Wrong course_key → 403 error with message about course key mismatch  
3. Missing token → 400 error
4. Invalid base64 token → 400 error
5. Invalid token format (no colon) → 400 error
6. User already has claims → Redirect to /login
7. Empty/null course_key → Treat as invalid
8. Token decode errors → 400 error

---

## URL Format

**Format:** `https://csci-e-11.org/login-direct?token=<base64(user_id:course_key)>`

**Example:**
- user_id: `abc123-def456-ghi789`
- course_key: `XYZ789`
- token_data: `abc123-def456-ghi789:XYZ789`
- token (base64): `YWJjMTIzLWRlZjQ1Ni1naGk3ODk6WFlaNzg5`
- URL: `https://csci-e-11.org/login-direct?token=YWJjMTIzLWRlZjQ1Ni1naGk3ODk6WFlaNzg5`

---

## Implementation Order

1. ✅ Add `get_user_from_user_id()` helper function
2. ✅ Add `generate_direct_login_url()` helper function
3. ✅ Implement `do_login_direct()` function
4. ✅ Add route in `lambda_handler()`
5. ✅ Modify `do_register_email()` to generate and display URL
6. ✅ Write comprehensive test suite
7. ✅ Run tests and fix any issues
8. ✅ Manual testing in staging environment

---

## Notes

- Using minimal claims approach: `claims={A.EMAIL: email}` instead of modifying function signature
- Token format: base64(user_id:course_key) for better security than email in URL
- Error message: Generic "Course key mismatch for email {email} or email is not registered." (doesn't reveal if email exists)
- Logging: Include "(direct_login)" in log messages to distinguish from OIDC sessions
- Redirect: Users with claims are redirected to /login (OIDC flow)
- All database operations use DynamoDB Local in tests (no mocking)

---

## Terminology Clarification

To avoid confusion between two different "register" operations:

- **`e11 register-email`** (Staff Command): Creates a student account in the database
  - Run by: Staff
  - Creates: User record with email + course_key (no claims, no preferred_name initially)
  - Purpose: Account creation
  - Used by: Staff to pre-create student accounts

- **`e11 register`** (Student Command): Registers a VM instance to an existing account
  - Run by: Student on their VM
  - Updates: User record with public_ip, preferred_name, hostname
  - Purpose: Instance/VM registration
  - Used by: Students to link their VM to their account

The direct login feature is for users whose accounts were created via `register-email` (staff account creation). These users can log in via the direct login URL, then later use `register` to register their VM instance if needed.
