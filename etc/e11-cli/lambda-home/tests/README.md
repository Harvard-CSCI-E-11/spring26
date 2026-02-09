# Testing Architecture

## How this works

* **Fake IdP**: Flask app serves discovery, /authorize (redirect back with code/state), /token (validates PKCE, signs an RS256 ID token), and /keys (JWKS).

* **DynamoDB Local**: Tests use DynamoDB Local (running on localhost:8000) via the `dynamodb_local` fixture. **We do NOT monkeypatch DynamoDB operations** - we use real DynamoDB Local tables with proper GSI indexes.

* **Mocked AWS Services**: The `fake_aws` fixture patches AWS service clients (Route53, SES, S3) but uses REAL DynamoDB Local tables for `users_table` and `sessions_table`.

* **End‑to‑end**: test_oidc_flow.py validates the stateless PKCE+state logic; test_home_handler.py hits your Lambda handler routes with synthetic API Gateway events.

## DynamoDB Testing Guidelines

**IMPORTANT: Use DynamoDB Local, NOT monkeypatching for DynamoDB.**

- Create actual records using functions like `create_new_user()` and `new_session()`
- Query the real DynamoDB Local tables - they have proper GSI indexes (GSI_Email)
- Do NOT mock `users_table.query` or `sessions_table.query` - use the real tables
- Use the `clean_dynamodb` fixture if you need a clean database state for each test

### Example

```python
def test_example(fake_aws, dynamodb_local):
    # ✅ CORRECT: Create actual records in DynamoDB Local
    test_email = "test@example.com"
    user = create_new_user(test_email, {"email": test_email, "name": "Test"})
    ses = new_session(event, {"email": test_email})

    # ✅ CORRECT: Query the real DynamoDB Local table
    user = get_user_from_email(test_email)

    # ❌ WRONG: Don't mock DynamoDB operations
    # users_table.query = MagicMock(...)  # DON'T DO THIS
```
