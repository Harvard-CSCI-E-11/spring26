# Testing Strategy for E11 CLI Main Functions

## Overview

This document outlines the strategy for improving test coverage of `e11/main.py`, specifically for:
- `do_register` - Registration command
- `do_config` - Configuration management command
- `do_grade` - Grading request command

## Current State

- `do_config`: No dedicated tests (only indirect testing via `test_e11_command.py`)
- `do_register`: No dedicated tests (only integration tests in `lambda-home/tests/test_registration_api.py`)
- `do_grade`: No dedicated tests

## Testing Approach

### 1. Testing `do_config`

**Strategy**: Direct unit testing with mocked file system

**Approach**:
- Use `tmp_path` fixture to create isolated config files
- Test all modes:
  - Interactive mode (no args): `get_answers()` flow
  - Get mode: `--get --section <section> --key <key>`
  - Set mode: `--section <section> --key <key> --setvalue <value>`
  - Email smashing: `--get --section student --key email --smash`

**Test Cases**:
- `test_do_config_interactive`: Test interactive configuration
- `test_do_config_get_value`: Test getting a config value
- `test_do_config_set_value`: Test setting a config value
- `test_do_config_get_email_smashed`: Test email smashing
- `test_do_config_new_section`: Test creating new sections
- `test_do_config_write_file`: Test config file writing

**Mocking**:
- Mock `input()` for interactive mode
- Use real file system with `tmp_path`

### 2. Testing `do_register`

**Strategy**: Integration testing with mocked HTTP requests that route to `lambda_handler`

**Approach**:
- Mock `requests.post` to intercept HTTP calls
- Instead of making real HTTP requests, create a Lambda event from the payload
- Call `lambda_handler` directly with the event
- Verify the response and side effects (DynamoDB updates, Route53 calls, emails)

**Key Components**:
- Use hard-coded email addresses and pre-assigned course keys (similar to `solve-lab1` script)
- Create test user in DynamoDB Local before registration
- Mock `get_public_ip()` and `get_instanceId()` to return test values
- Mock `on_ec2()` to return `True` (or use `--force` flag)

**Test Cases**:
- `test_do_register_success`: Successful registration flow
- `test_do_register_missing_config`: Missing required config fields
- `test_do_register_invalid_email`: Invalid email address
- `test_do_register_ip_mismatch`: IP address mismatch (with and without `--fixip`)
- `test_do_register_invalid_course_key`: Invalid course key length
- `test_do_register_retry_on_timeout`: Retry logic on timeout
- `test_do_register_http_error`: HTTP error handling
- `test_do_register_verbose_mode`: Verbose vs quiet mode

**Mocking Strategy**:
```python
def mock_requests_post(monkeypatch, lambda_handler):
    """Mock requests.post to route to lambda_handler instead"""
    def mock_post(url, json=None, timeout=None):
        # Convert JSON payload to Lambda event
        event = create_lambda_event_from_payload(url, json)
        # Call lambda_handler
        response = lambda_handler(event, None)
        # Convert Lambda response to requests.Response
        return convert_lambda_response_to_requests_response(response)
    monkeypatch.setattr(requests, 'post', mock_post)
```

**Dependencies**:
- DynamoDB Local (via `dynamodb_local` fixture)
- Lambda handler from `lambda-home` (import `home_app.home.lambda_handler`)
- Test utilities from `lambda-home/tests/test_utils.py`

### 3. Testing `do_grade`

**Strategy**: Integration testing with mocked HTTP requests and SSH operations

**Approach**:
- Mock `requests.post` to intercept HTTP calls and route to `lambda_handler`
- Mock SSH operations (`grader.grade_student_vm`) since Lambda can't SSH into VMs
- Test both modes:
  - Normal mode: HTTP POST to API endpoint
  - Direct mode: `--direct <ip>` with SSH key

**Test Cases**:
- `test_do_grade_success`: Successful grading request
- `test_do_grade_missing_config`: Missing course_key or email
- `test_do_grade_http_error`: HTTP error handling
- `test_do_grade_timeout`: Timeout handling
- `test_do_grade_direct_mode`: Direct grading mode (mocked SSH)
- `test_do_grade_verbose_mode`: Verbose output
- `test_do_grade_debug_mode`: Debug output (JSON dump)

**Mocking Strategy**:
```python
# Mock HTTP requests (same as do_register)
mock_requests_post(monkeypatch, lambda_handler)

# Mock SSH/grader operations
def mock_grade_student_vm(monkeypatch):
    """Mock grader.grade_student_vm to return test results"""
    def mock_grade(email, public_ip, lab, pkey_pem=None, key_filename=None):
        return {
            'error': False,
            'fails': 0,
            'passes': 5,
            'tests': [...],
            'score': 100
        }
    monkeypatch.setattr(grader, 'grade_student_vm', mock_grade)
```

**Dependencies**:
- DynamoDB Local
- Lambda handler
- Mock grader results

## Test File Structure

Create `tests/test_main_commands.py`:

```python
"""
Tests for e11/main.py command functions:
- do_config
- do_register
- do_grade
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from e11 import main
from e11.support import get_config, config_path
# Import lambda handler for integration testing
import sys
from pathlib import Path

# Add lambda-home to path for integration tests
lambda_home_path = Path(__file__).parent.parent / "lambda-home" / "src"
if str(lambda_home_path) not in sys.path:
    sys.path.insert(0, str(lambda_home_path))

# Test fixtures and utilities
# ...

class TestDoConfig:
    """Tests for do_config command"""
    # ...

class TestDoRegister:
    """Tests for do_register command"""
    # ...

class TestDoGrade:
    """Tests for do_grade command"""
    # ...
```

## Test Utilities

Create helper functions in `tests/test_main_commands.py`:

```python
def create_test_config_file(tmp_path, email, course_key, public_ip="1.2.3.4", instance_id="i-1234567890abcdef0"):
    """Create a test config file"""
    config_path = tmp_path / "e11-config.ini"
    config_path.write_text(f"""[student]
email = {email}
course_key = {course_key}
public_ip = {public_ip}
instanceId = {instance_id}
preferred_name = Test User
""")
    return config_path

def create_lambda_event_from_payload(endpoint_url, payload):
    """Convert a requests.post payload to a Lambda event"""
    # Extract path from endpoint URL
    # Create Lambda HTTP API v2 event structure
    # ...

def convert_lambda_response_to_requests_response(lambda_response):
    """Convert Lambda response to requests.Response object"""
    # Create Mock requests.Response
    # ...
```

## Integration with Existing Tests

- Reuse fixtures from `lambda-home/tests/conftest.py`:
  - `dynamodb_local`
  - `fake_aws`
  - `clean_dynamodb`
- Reuse utilities from `lambda-home/tests/test_utils.py`:
  - `create_new_user`
  - `create_lambda_event`
  - `create_test_config_data`
  - `create_test_auth_data`

## Hard-coded Test Data (Similar to solve-lab1)

Use pre-assigned course keys and test emails:
- Test email: `test-{uuid}@example.com` (unique per test)
- Course key: Generated via `create_new_user()` or hard-coded test key
- Public IP: `1.2.3.4` (mocked)
- Instance ID: `i-1234567890abcdef0` (mocked)

## Running Tests

```bash
# Run all main command tests
pytest tests/test_main_commands.py -v

# Run specific test class
pytest tests/test_main_commands.py::TestDoConfig -v

# Run with coverage
pytest tests/test_main_commands.py --cov=e11.main --cov-report=term
```

## Implementation Plan

1. **Phase 1: Test Infrastructure**
   - Create `tests/test_main_commands.py`
   - Implement helper functions for mocking HTTP requests
   - Implement helper functions for creating test configs
   - Set up integration with lambda-home handler

2. **Phase 2: Test `do_config`**
   - Implement all `do_config` test cases
   - Verify file operations work correctly
   - Test edge cases (missing sections, invalid keys, etc.)

3. **Phase 3: Test `do_register`**
   - Implement HTTP request mocking that routes to `lambda_handler`
   - Implement all `do_register` test cases
   - Verify integration with DynamoDB Local
   - Test error cases and retry logic

4. **Phase 4: Test `do_grade`**
   - Implement HTTP request mocking
   - Implement SSH/grader mocking
   - Implement all `do_grade` test cases
   - Test both normal and direct modes

5. **Phase 5: Integration Testing**
   - Test full flows: `do_register` → `lambda_handler` → `api_register`
   - Test full flows: `do_grade` → `lambda_handler` → `api_grader`
   - Verify end-to-end behavior

## Success Criteria

- All three functions have comprehensive test coverage
- Tests use real DynamoDB Local (not mocked)
- Tests intercept HTTP requests and route to `lambda_handler`
- Tests use hard-coded email addresses and pre-assigned course keys
- All tests pass and provide meaningful coverage metrics

