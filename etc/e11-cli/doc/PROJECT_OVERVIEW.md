# E11 CLI Project Overview

## Introduction

The E11 CLI project is a comprehensive system for managing CSCI E-11 course infrastructure, student AWS instance management, and automated lab grading. The system consists of two main components:

1. **E11 CLI** (`e11/`) - A command-line tool installed on student VMs that manages instance access, configuration, and local testing
2. **Lambda-Home** (`lambda-home/`) - An AWS Lambda function that powers the student dashboard (https://csci-e-11.org/) and performs remote grading

Both components share the `e11` Python module, which provides core functionality for grading, SSH access, and configuration management.

## Project Structure

```
e11-cli/
├── e11/                          # Main CLI package
│   ├── __init__.py
│   ├── __main__.py               # Entry point for 'e11' command
│   ├── main.py                   # Main CLI command handler
│   ├── support.py                # Utility functions for file/config access
│   ├── doctor.py                 # System diagnostic tool
│   ├── staff.py                  # Staff-only commands (when E11_STAFF env var set)
│   ├── e11_common.py             # Shared DynamoDB and AWS utilities
│   ├── e11core/                  # Core grader framework
│   │   ├── assertions.py         # Test assertion helpers
│   │   ├── config.py             # E11Config class for configuration
│   │   ├── constants.py          # Project constants (course name, domain, etc.)
│   │   ├── context.py            # E11Context dataclass for passing lab context
│   │   ├── decorators.py         # @timeout and @retry decorators
│   │   ├── e11ssh.py             # SSH connection wrapper for remote grading
│   │   ├── grader.py             # Test discovery and execution framework
│   │   ├── render.py             # Grade report rendering
│   │   ├── testrunner.py         # TestRunner class (local/remote execution)
│   │   └── utils.py              # Logging and utility functions
│   └── lab_tests/                # Lab test definitions
│       ├── lab_common.py         # Shared test functions across labs
│       ├── lab0_test.py          # Lab 0 tests
│       ├── lab1_test.py          # Lab 1 tests
│       └── ...                   # Additional lab test files
├── lambda-home/                  # AWS Lambda dashboard application
│   ├── src/
│   │   └── home_app/
│   │       ├── home.py           # Main Lambda handler
│   │       ├── oidc.py           # OIDC authentication for Harvard Key
│   │       ├── sessions.py       # Session management
│   │       ├── common.py         # Shared utilities
│   │       ├── templates/        # Jinja2 HTML templates
│   │       └── static/           # Static CSS/HTML files
│   ├── template.yaml             # AWS SAM template
│   └── tests/                    # Lambda-home test suite
├── lambda-users-db/              # SAM template for DynamoDB table creation
├── tests/                        # E11 CLI test suite
├── pyproject.toml                # Poetry configuration
├── Makefile                      # Build and test automation
├── README.md                     # User-facing documentation
├── TESTING.md                    # Testing documentation
└── NOTES.md                      # Developer notes

```

## Core Components

### 1. E11 CLI (`e11/`)

The E11 CLI is a Python package that provides command-line tools for students to manage their AWS instances and test their lab assignments.

#### Main Commands

- **`e11 config`** - Edit configuration variables stored in `/home/ubuntu/e11-config.ini`
- **`e11 register`** - Register instance with CSCI E-11 infrastructure (sets up DNS)
- **`e11 status`** - Display instance status and configuration
- **`e11 access [on|off|check]`** - Control SSH access for course staff
- **`e11 check [labN]`** - Run local lab tests
- **`e11 answer [labN]`** - Answer additional questions for specific labs
- **`e11 version`** - Show version information
- **`e11 doctor`** - Run system diagnostics

#### Core Modules

##### `e11core/grader.py`
The grading framework that:
- Discovers test functions in lab test modules
- Executes tests in definition order
- Collects results and calculates scores
- Works both locally (`e11 check`) and remotely (via SSH for grading)

##### `e11core/testrunner.py`
Provides a unified interface for test execution that abstracts local vs. remote execution:
- `run_command()` - Execute shell commands (local subprocess or remote SSH)
- `read_file()` - Read files (local file system or remote SFTP)
- `http_get()` - Make HTTP requests with TLS certificate validation
- `port_check()` - Check if a port is open

##### `e11core/context.py`
Defines the `E11Context` dataclass that carries lab-specific information:
- Lab name, number, and directory path
- Student information (email, course key, public IP)
- DNS names for the lab
- API keys and database paths (for specific labs)
- Dynamic fields for lab-specific data

##### `e11core/e11ssh.py`
SSH connection wrapper using Paramiko:
- Manages SSH connections for remote grading
- Supports both key files and PEM-formatted keys
- Provides command execution and SFTP file access
- Context manager support for automatic cleanup

### 2. Lambda-Home (`lambda-home/`)

An AWS Lambda function that provides:

#### Features

- **Student Dashboard** - Web interface at https://csci-e-11.org/
- **OIDC Authentication** - Harvard Key integration for student login
- **Instance Registration** - Handles student VM registration and DNS setup
- **Remote Grading** - SSH into student VMs and execute lab tests
- **Grade Storage** - Stores grading results in DynamoDB
- **Email Notifications** - Sends grade reports to students via SES

#### Main Handler (`home.py`)

Routes HTTP requests to appropriate handlers:
- `/` - Dashboard home page
- `/login` - OIDC authentication initiation
- `/callback` - OIDC callback handler
- `/dashboard` - Student dashboard (requires authentication)
- `/logout` - Session termination
- `/api/v1` - JSON API endpoints:
  - `register` - Instance registration
  - `grade` - Request lab grading
  - `check-access` - Verify SSH access
  - `version` - Version information

#### Data Storage

Uses AWS DynamoDB with two tables:
- **e11-users** - User profiles, registration info, and grade history
- **home-app-sessions** - Active user sessions

### 3. Lab Tests (`e11/lab_tests/`)

Lab tests are Python modules that define test functions for each lab assignment. Tests verify:

- Configuration correctness (SSH keys, nginx config, etc.)
- Service functionality (web servers, databases, etc.)
- Security settings (file permissions, user accounts, etc.)
- Network services (DNS, HTTPS, API endpoints, etc.)

Tests are designed to work in two contexts:
1. **Local execution** - When students run `e11 check labN` on their VM
2. **Remote execution** - When graders SSH into student VMs for grading

## Architecture

### Student Workflow

1. **Setup**: Student launches AWS EC2 instance
2. **Configuration**: Student runs `e11 config` to enter email and preferences
3. **Registration**: Student runs `e11 register` which:
   - Validates configuration
   - Sends registration to Lambda-Home API
   - Lambda creates DNS records in Route53
   - Student receives confirmation email with course key
4. **Lab Work**: Student completes lab assignments
5. **Testing**: Student runs `e11 check labN` to test locally
6. **Grading**: Student requests grading via dashboard or `e11 grade labN`

### Grading Workflow

1. **Request**: Student requests grading via Lambda dashboard
2. **Authentication**: Lambda validates student's course key
3. **SSH Connection**: Lambda uses bot SSH key to connect to student's VM
4. **Test Execution**: Lambda runs lab tests remotely via SSH
5. **Result Storage**: Grades stored in DynamoDB
6. **Notification**: Student receives email with grade report

### Test Execution Flow

1. **Context Building**: `build_ctx()` creates `E11Context` with lab information
2. **TestRunner Creation**: 
   - Local: `TestRunner(ctx)` - uses subprocess/file access
   - Remote: `TestRunner(ctx, ssh=E11Ssh(...))` - uses SSH
3. **Test Discovery**: Module scanner finds all `test_*` functions
4. **Test Execution**: Each test runs with timeout protection
5. **Result Collection**: Results aggregated into summary dictionary
6. **Score Calculation**: `5.0 * (passes / total_tests)`

## Key Design Patterns

### Dual Execution Model

The same test code works both locally and remotely by using the `TestRunner` abstraction:
- Local mode: Direct subprocess and file system access
- Remote mode: SSH commands and SFTP file access
- Tests are written once and work in both contexts

### Context Object Pattern

The `E11Context` dataclass carries all lab-specific information:
- Type-safe access to lab properties
- Backward-compatible dict-like access for legacy code
- Dynamic fields for lab-specific extensions
- JSON serializable for API responses

### Test Discovery Pattern

Tests are discovered dynamically using Python's importlib:
- Tests are functions named `test_*` in modules named `labN_test.py`
- No need to maintain explicit test registries
- Tests execute in definition order (allowing dependencies)

## Configuration

### Student Configuration (`e11-config.ini`)

Located at `/home/ubuntu/e11-config.ini`, contains:
- `[student]` section with:
  - `email` - Student email address
  - `preferred_name` - Display name
  - `public_ip` - EC2 instance public IP
  - `instanceId` - EC2 instance ID
  - `course_key` - 6-character course key (from registration)

### Environment Variables

- **`E11_STAFF`** - Enables staff-only commands when set
- **`E11_CONFIG`** - Override config file path
- **`LOG_LEVEL`** - Logging level (DEBUG, INFO, WARNING, ERROR)
- **`HOME`** - Home directory (may be monkeypatched in tests)

## Dependencies

### E11 CLI Core
- Python 3.12+
- boto3 - AWS SDK
- paramiko - SSH client
- requests - HTTP client
- dnspython - DNS operations
- email-validator - Email validation
- pydantic - Data validation
- pyyaml - YAML parsing
- jinja2 - Template rendering
- crossplane - Nginx config parsing

### Lambda-Home
- Python 3.13 (Lambda runtime)
- All E11 CLI dependencies
- Additional AWS service integrations (DynamoDB, SES, Route53, Secrets Manager)

## Testing

See `TESTING.md` for comprehensive testing documentation. Key points:

- **E11 CLI Tests**: Located in `tests/`, run with `make check`
- **Lambda-Home Tests**: Located in `lambda-home/tests/`, run with `cd lambda-home && make check`
- **Test Coverage Goals**: 
  - E11 CLI: 70%+
  - Lambda-Home: 85%+

## Deployment

### E11 CLI

Installed on student VMs via `pipx` using the installation script:
```bash
pipx install /path/to/e11-cli
```

The wheel file is built and distributed from the GitHub repository.

### Lambda-Home

Deployed via AWS SAM (Serverless Application Model):
```bash
cd lambda-home
make prod-vbd  # Build, validate, and deploy to production
make stage-vbd # Build, validate, and deploy to staging
```

Pre-deployment checks include:
- Full static analysis (pylint, pyright, ruff, djlint)
- All tests passing
- Coverage thresholds met

## Development Notes

### Code Quality

- Uses `pylint` for static analysis
- Uses `pyright` for type checking
- Uses `ruff` for fast linting and formatting
- Uses `pytest` for testing with coverage reporting

### Known Technical Debt

- `context.py` should be folded into `config.py` (noted in README)
- `render.py` should be moved into `grader.py` (noted in README)
- `utils.py` and `constants.py` could be merged into `common.py` (noted in README)
- Not all uses of 'spring26' are fully parameterized (noted in constants.py)

### Future Improvements

- Increase test coverage for E11 CLI
- Add DynamoDBLocal integration for more accurate testing
- Add SSH testing capabilities
- More comprehensive integration tests
- Performance testing for critical paths
- Security testing for authentication flows

## Related Documentation

- `README.md` - User-facing documentation
- `TESTING.md` - Comprehensive testing guide
- `NOTES.md` - Developer notes and lessons learned
- `e11/lab_tests/README.md` - Lab test writing guide
- `lambda-home/STAGING.md` - Staging environment documentation

## Support and Contact

For issues or questions:
- Course staff: See course communication channels
- Technical issues: GitHub repository issues
- Author: Simson Garfinkel <simsong@acm.org>

