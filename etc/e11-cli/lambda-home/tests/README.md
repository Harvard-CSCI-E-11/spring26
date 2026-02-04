# Lambda-Home Test Suite

This directory contains the test suite for Lambda-Home, the AWS Lambda function that powers the CSCI E-11 student dashboard.

## Prerequisites

- **Python 3.13+** with Poetry installed
- **Java** (for DynamoDB Local): `brew install openjdk`
- **DynamoDB Local** must be running before executing tests

## Running Tests

```bash
# 1. Start DynamoDB Local (from etc/e11-cli directory)
cd /path/to/e11-spring26-dev/etc/e11-cli
make start_local_dynamodb

# 2. Run all tests (from lambda-home directory)
cd lambda-home
poetry run pytest tests/ -v

# 3. Run a specific test file
poetry run pytest tests/test_oidc_flow.py -v

# 4. Run with coverage
poetry run pytest tests/ --cov=home_app

# 5. Stop DynamoDB Local when done
make stop_local_dynamodb
```

---

## Test Infrastructure

### DynamoDB Local

Tests use **real DynamoDB Local** tables (not mocks) for accurate integration testing. The `dynamodb_local` fixture in `conftest.py`:
- Creates `e11-users` and `home-app-sessions` tables with proper GSI indexes
- Cleans up data between test sessions
- Runs on `http://localhost:8010`

**IMPORTANT: Use DynamoDB Local, NOT monkeypatching for DynamoDB.**

- Create actual records using functions like `create_new_user()` and `new_session()`
- Query the real DynamoDB Local tables - they have proper GSI indexes (GSI_Email)
- Do NOT mock `users_table.query` or `sessions_table.query` - use the real tables
- Use the `clean_dynamodb` fixture if you need a clean database state for each test

```python
def test_example(fake_aws, dynamodb_local):
    # CORRECT: Create actual records in DynamoDB Local
    test_email = "test@example.com"
    user = create_new_user(test_email, {"email": test_email, "name": "Test"})
    ses = new_session(event, {"email": test_email})

    # CORRECT: Query the real DynamoDB Local table
    user = get_user_from_email(test_email)

    # WRONG: Don't mock DynamoDB operations
    # users_table.query = MagicMock(...)  # DON'T DO THIS
```

### Fake OIDC Identity Provider

The `fake_idp.py` module implements a minimal OIDC provider for testing Harvard Key authentication:
- Provides discovery, authorization, token, and JWKS endpoints
- Generates real RS256-signed JWTs
- Supports PKCE verification
- Runs as a local Flask server during tests

### Key Fixtures (conftest.py)

| Fixture | Scope | Description |
|---------|-------|-------------|
| `fake_idp_server` | session | Starts the fake OIDC identity provider |
| `dynamodb_local` | session | Ensures DynamoDB Local is running with proper tables |
| `clean_dynamodb` | function | Cleans tables before/after each test |
| `fake_aws` | function | Mocks Secrets Manager, Route53, SES, S3 while using real DynamoDB |

### Test Utilities (test_utils.py)

Helper functions and classes for test consistency:

- **`MockedAWSServices`**: Tracks Route53 and SES calls for verification
- **`create_test_config_data()`**: Factory for test configuration data
- **`create_test_auth_data()`**: Factory for authentication payloads
- **`create_registration_payload()`**: Builds registration request payloads
- **`create_lambda_event()`**: Creates Lambda event structures
- **`assert_route53_called()`**: Verifies DNS record creation
- **`assert_ses_email_sent()`**: Verifies email sending
- **`assert_response_success()`**: Validates successful API responses

---

## Test File Catalogue

### test_home_handler.py

**Purpose**: End-to-end Lambda handler testing with full OIDC flow.

| Test | Description |
|------|-------------|
| `test_lambda_routes_without_aws` | Tests complete user journey: home page, OIDC login, callback, dashboard, logout |

---

### test_registration_api.py

**Purpose**: Registration API endpoint testing for all user flows.

| Test | Description |
|------|-------------|
| `test_registration_api_flow` | First-time user registration: creates user, DNS records, sends confirmation email |
| `test_registration_api_invalid_user` | Rejects registration for non-existent email (403) |
| `test_registration_api_invalid_course_key` | Rejects registration with wrong course_key (403) |
| `test_registration_api_returning_user_flow` | Returning user registration: updates existing user, creates new DNS records |

---

### test_oidc_flow.py

**Purpose**: OIDC authentication flow validation.

| Test | Description |
|------|-------------|
| `test_end_to_end_oidc_stateless` | Complete OIDC flow: authorization URL, IdP redirect, code exchange, token verification |

---

### test_oidc_negatives.py

**Purpose**: OIDC error handling and security validation.

| Test | Description |
|------|-------------|
| `test_invalid_state_signature` | Rejects callback with corrupted state signature (BadSignature) |
| `test_expired_state` | Rejects callback with expired state token (SignatureExpired) |
| `test_pkce_mismatch_with_swapped_state` | Rejects mismatched code/state from different auth requests (PKCE failure) |

---

### test_direct_login.py

**Purpose**: Direct login functionality for staff-created accounts (without OIDC claims).

| Test | Description |
|------|-------------|
| `test_direct_login_success` | Successful login with valid token redirects to dashboard |
| `test_direct_login_missing_token` | Returns 400 for missing token parameter |
| `test_direct_login_invalid_token_format` | Returns 400 for malformed base64 token |
| `test_direct_login_invalid_user_id` | Returns 403 for non-existent user_id |
| `test_direct_login_invalid_course_key` | Returns 403 for wrong course_key |
| `test_direct_login_user_has_claims` | Redirects OIDC users to /login instead |
| `test_direct_login_session_created_in_db` | Verifies session creation in DynamoDB |
| `test_direct_login_can_access_dashboard` | End-to-end: login then dashboard access with cookie |
| `test_generate_direct_login_url` | Validates URL generation function |
| `test_direct_login_invalid_token_no_colon` | Returns 400 for token without colon separator |

---

### test_dashboard_page_routing.py

**Purpose**: Dashboard page routing with query parameters.

| Test | Description |
|------|-------------|
| `test_dashboard_page_routing[terms.html]` | `/dashboard?page=terms.html` returns terms template |
| `test_dashboard_page_routing[privacy.html]` | `/dashboard?page=privacy.html` returns privacy template |
| `test_dashboard_page_routing[help.html]` | `/dashboard?page=help.html` returns help template |
| `test_dashboard_page_routing[about.html]` | `/dashboard?page=about.html` returns about template |

---

### test_redirects_and_routes.py

**Purpose**: HTTP routing, redirects, and utility function testing.

| Test | Description |
|------|-------------|
| `test_all_lab_redirects_exist` | Validates LAB_REDIRECTS has entries for labs 0-8 |
| `test_lab_redirects_return_valid_redirects` | All `/labN` routes return 302 with correct Location |
| `test_version_endpoint` | `/version` returns 200 with version info |
| `test_heartbeat_endpoint` | `/heartbeat` returns valid response structure |
| `test_404_for_unknown_paths` | Unknown paths return 404 |
| `test_404_for_unknown_methods` | Unsupported HTTP methods return 404 |
| `test_static_file_404_for_nonexistent` | Non-existent static files return 404 |
| `test_root_path_returns_response` | Root path returns valid response |
| `test_logout_path_returns_response` | `/logout` returns valid response |
| `test_lab_redirects_are_unique` | All lab redirect URLs are unique |
| `test_parse_event_*` | Event parsing tests (method, path, payload, base64, stage prefix) |
| `test_parse_s3_event_*` | S3 event detection tests |
| `test_is_sqs_event_*` | SQS event detection tests |
| `test_is_staging_environment` | Staging environment detection |
| `test_make_cookie_*` | Cookie creation tests |
| `test_get_cookie_domain` | Cookie domain selection by environment |
| `test_resp_json_creates_valid_response` | JSON response formatting |
| `test_redirect_creates_valid_redirect` | Redirect response formatting |
| `test_error_404_creates_valid_error` | 404 error response formatting |
| `test_parse_cookies_*` | Cookie parsing tests |
| `test_expire_batch_*` | Session expiration tests |
| `test_eastern_filter_*` | Timestamp formatting filter tests |
| `test_validate_payload_structure` | Payload validation for API requests |
| `test_domain_suffixes_constant` | DOMAIN_SUFFIXES has 9 entries |
| `test_resp_text_*` | Text/HTML response formatting tests |
| `test_resp_png_*` | PNG response tests |
| `test_api_dispatch_*` | API dispatch routing tests |

---

### test_queue_grade.py

**Purpose**: SQS-based grading queue functionality.

| Test | Description |
|------|-------------|
| `test_queue_grade_sends_message` | `queue_grade()` sends properly formatted SQS message |
| `test_queue_grade_handles_sqs_event` | Full flow: queue, SQS event processing, email sent |

---

### test_lab_config.py

**Purpose**: Lab configuration, deadlines, and next_lab computation.

| Test | Description |
|------|-------------|
| `test_lab_config_structure` | LAB_CONFIG has correct structure for labs 0-8 |
| `test_lab_config_backward_compatibility` | LAB_REDIRECTS matches LAB_CONFIG redirects |
| `test_lab_redirects_still_work` | Lab redirects work with LAB_CONFIG |
| `test_api_grader_before_deadline[lab0-2]` | Grading accepted before deadline (parametrized) |
| `test_api_grader_after_deadline_rejects[lab0-2]` | Grading rejected after deadline (parametrized) |
| `test_api_grader_sqs_bypasses_deadline` | SQS requests bypass deadline checks |
| `test_do_dashboard_computes_next_lab` | Dashboard correctly computes next_lab |
| `test_do_dashboard_no_next_lab_when_all_past` | Dashboard handles all labs past deadline |
| `test_lab_name_normalization` | Lab name normalization (e.g., "1" to "lab1") |

---

### test_import_validation.py

**Purpose**: Validates Lambda handler imports work correctly with vendored wheel.

| Test | Description |
|------|-------------|
| `test_lambda_handler_imports` | Lambda handler module imports successfully |
| `test_grader_imports_s3_bucket_correctly` | Grader imports S3_BUCKET from correct module |

---

### test_staging_environment.py

**Purpose**: Staging environment detection and cookie domain handling.

| Test | Description |
|------|-------------|
| `test_is_staging_environment` | Staging detection for prod/stage/no-stage events |
| `test_get_cookie_domain` | Cookie domain selection for prod/staging |
| `test_make_cookie_with_dynamic_domain` | Cookie creation uses correct domain |
| `test_environment_detection_integration` | Full event structure environment detection |

---

### test_e11_registration_integration.py

**Purpose**: End-to-end integration test for e11 CLI registration flow.

| Test | Description |
|------|-------------|
| `test_e11_registration_with_test_config` | Simulates full CLI to API to DynamoDB registration flow |

---

## Test Counts by File

| File | Tests |
|------|-------|
| test_redirects_and_routes.py | 46 |
| test_lab_config.py | 13 |
| test_direct_login.py | 10 |
| test_dashboard_page_routing.py | 4 |
| test_staging_environment.py | 4 |
| test_registration_api.py | 4 |
| test_oidc_negatives.py | 3 |
| test_import_validation.py | 2 |
| test_queue_grade.py | 2 |
| test_home_handler.py | 1 |
| test_oidc_flow.py | 1 |
| test_e11_registration_integration.py | 1 |
| **Total** | **91** |
