# E11 Project Architecture

## Overview

The E11 project is a comprehensive system for managing CSCI E-11 course infrastructure, student AWS instance management, and automated lab grading. The system consists of multiple components that share a common codebase through a vendored Python wheel.

## Project Structure

```
e11-cli/
├── e11/                          # Main CLI package (source code)
│   ├── __init__.py
│   ├── __main__.py               # Entry point for 'e11' command
│   ├── main.py                   # Main CLI command handler (do_register, do_grade, do_config, etc.)
│   ├── support.py                # Utility functions for file/config access
│   ├── doctor.py                 # System diagnostic tool
│   ├── staff.py                  # Staff-only commands
│   ├── e11_common.py             # Shared DynamoDB and AWS utilities
│   ├── e11core/                  # Core grader framework
│   │   ├── assertions.py         # Test assertion helpers
│   │   ├── config.py             # E11Config class for configuration
│   │   ├── constants.py          # Project constants (course name, domain, etc.)
│   │   ├── context.py            # E11Context dataclass for passing lab context
│   │   ├── decorators.py         # @timeout and @retry decorators
│   │   ├── e11ssh.py             # SSH connection wrapper for remote grading
│   │   ├── grader.py             # Test discovery and execution framework
│   │   ├── testrunner.py         # TestRunner class (local/remote execution)
│   │   └── utils.py              # Logging and utility functions
│   └── lab_tests/                # Lab test definitions
│       ├── lab_common.py         # Shared test functions across labs
│       ├── lab0_test.py          # Lab 0 tests
│       └── ...                   # Additional lab test files
├── lambda-home/                  # AWS Lambda dashboard application
│   ├── src/
│   │   └── home_app/
│   │       ├── home.py           # Main Lambda handler
│   │       ├── api.py            # API endpoint handlers (api_register, api_grader, etc.)
│   │       ├── oidc.py           # OIDC authentication for Harvard Key
│   │       ├── sessions.py       # Session management
│   │       ├── common.py         # Shared utilities
│   │       ├── templates/        # Jinja2 HTML templates
│   │       └── static/           # Static CSS/HTML files
│   ├── src/home_app/e11.whl      # VENDORED: Copy of e11 wheel (built from ../e11/)
│   ├── template.yaml             # AWS SAM template
│   └── tests/                    # Lambda-home test suite
├── lambda-leaderboard/            # AWS Lambda leaderboard application
│   ├── src/
│   │   └── leaderboard_app/
│   │       └── ...
│   ├── src/leaderboard_app/e11.whl  # VENDORED: Copy of e11 wheel
│   └── tests/
└── tests/                        # E11 CLI test suite
```

## Critical Architecture Notes for Cursor

### 1. Shared Codebase via Vendored Wheel

**IMPORTANT**: The `e11/` and `e11core/` directories contain the source code that is:
1. Built into a Python wheel (`dist/e11-*.whl`)
2. Vended (copied) into `lambda-home/src/home_app/e11.whl` and `lambda-leaderboard/src/leaderboard_app/e11.whl`
3. Used by both the CLI tool (installed on student VMs) and the Lambda functions

**When making changes to `e11/` or `e11core/`:**
- These changes impact **both** the CLI tool and the Lambda functions
- After modifying `e11/` or `e11core/`, you must:
  1. Rebuild the wheel: `poetry build` (or `make` in root)
  2. Re-vend the wheel: `cd lambda-home && make vend-e11` and `cd lambda-leaderboard && make vend-e11`
  3. Test both the CLI and Lambda functions

**The vendoring process:**
- Root `Makefile` or `poetry build` creates `dist/e11-*.whl`
- `lambda-home/Makefile` target `vend-e11` copies the wheel to `src/home_app/e11.whl`
- `lambda-leaderboard/Makefile` target `vend-e11` copies the wheel to `src/leaderboard_app/e11.whl`
- Lambda functions import from the vendored wheel: `from e11.e11_common import ...`

### 2. Component Responsibilities

#### E11 CLI (`e11/main.py`)
- **do_register**: Validates config, sends HTTP POST to `API_ENDPOINT` with `action='register'`
- **do_grade**: Sends HTTP POST to `API_ENDPOINT` with `action='grade'` (or does direct grading via SSH)
- **do_config**: Reads/writes `/home/ubuntu/e11-config.ini` file
- **do_check**: Runs local lab tests
- **do_access**: Manages SSH access for course staff

#### Lambda-Home (`lambda-home/src/home_app/`)
- **lambda_handler**: Main entry point, routes HTTP requests
- **api_register**: Handles registration requests from `do_register`
- **api_grader**: Handles grading requests from `do_grade`, SSHs into student VMs
- **do_dashboard**: Renders student dashboard
- Uses DynamoDB for user data, sessions, grades
- Uses Route53 for DNS management
- Uses SES for email notifications

#### Lambda-Leaderboard (`lambda-leaderboard/src/leaderboard_app/`)
- Displays course leaderboard
- Also uses vendored `e11.whl` for shared utilities

### 3. Data Flow

#### Registration Flow
1. Student runs `e11 register` on their VM
2. `do_register()` validates config, creates payload
3. HTTP POST to `https://csci-e-11.org/api/v1` with `action='register'`
4. Lambda `lambda_handler` routes to `api.dispatch("POST", "register", ...)`
5. `api_register()` creates/updates DynamoDB user record, creates Route53 DNS records
6. Sends confirmation email via SES

#### Grading Flow
1. Student runs `e11 grade lab1` on their VM (or requests via dashboard)
2. `do_grade()` creates payload with auth credentials
3. HTTP POST to `https://csci-e-11.org/api/v1` with `action='grade'`
4. Lambda `lambda_handler` routes to `api.dispatch("POST", "grade", ...)`
5. `api_grader()` SSHs into student VM using `grader.grade_student_vm()`
6. Executes lab tests, stores results in DynamoDB
7. Sends grade report email via SES

### 4. Testing Philosophy

- **E11 CLI tests** (`tests/`): Test CLI commands in isolation
- **Lambda-Home tests** (`lambda-home/tests/`): Test Lambda handlers with DynamoDB Local
- **Integration tests**: Test full flows (e.g., `do_register` → `lambda_handler` → `api_register`)

**Key Testing Principles:**
- Use DynamoDB Local for all DynamoDB operations (never mock DynamoDB)
- Mock external HTTP calls (Route53, SES) but use real DynamoDB Local
- For testing `do_register` and `do_grade`, intercept HTTP requests and route to `lambda_handler` instead
- Use hard-coded email addresses and pre-assigned course keys (similar to `solve-lab1` script)

### 5. Configuration Management

- Student config: `/home/ubuntu/e11-config.ini` (ConfigParser format)
- Contains: `email`, `preferred_name`, `course_key`, `public_ip`, `instanceId`
- Can be set via `e11 config` command or directly edited
- For testing: Use `E11_CONFIG` environment variable to point to test config file

### 6. Dependencies

- **E11 CLI**: Python 3.12 (Ubuntu 24.04)
- **Lambda-Home**: Python 3.13 (AWS Lambda runtime)
- **Lambda-Leaderboard**: Python 3.13 (AWS Lambda runtime)
- Shared dependencies: boto3, requests, paramiko, jinja2, etc.

## Development Workflow

1. **Make changes to `e11/` or `e11core/`**
2. **Rebuild and re-vend the wheel:**
   ```bash
   poetry build
   cd lambda-home && make vend-e11
   cd ../lambda-leaderboard && make vend-e11
   ```
3. **Test both CLI and Lambda:**
   ```bash
   # Test CLI
   make check

   # Test Lambda-Home
   cd lambda-home && make check
   ```

## Important Reminders

- **Never modify code in `lambda-home/src/home_app/e11/` or `lambda-leaderboard/src/leaderboard_app/e11/`** - these are vendored wheels, not source code
- **Always re-vend after changing `e11/` or `e11core/`**
- **Changes to `e11/` or `e11core/` affect both CLI and Lambda functions**
- **Use DynamoDB Local for testing, never mock DynamoDB operations**
- **For integration testing, intercept HTTP requests and route to `lambda_handler`**

