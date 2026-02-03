This directory contains the following:
* e11/ - The source code for the e11 command
* lambda-home/ - The AWS Lambda function at https://csci-e-11.org/ (dashboard, registration, grading)
* lambda-leaderboard/ - The AWS Lambda function for the course leaderboard
* lambda-users-db/ - The SAM template for creating the e11-users DynamoDB table
* tests/ - Tests for the e11 CLI and grader system

You will also find in this directory:
* e11/__main__.py - Entry point for the e11 command
* e11/main.py - Main CLI command handler
* e11/e11core/ - Core grader framework modules
  * assertions.py - Test assertion helpers
  * config.py - E11Config class for configuration
  * constants.py - Project constants (course name, domain, etc.)
  * context.py - E11Context dataclass for passing lab context
  * decorators.py - @timeout and @retry decorators
  * e11ssh.py - SSH connection wrapper for remote grading
  * grader.py - Test discovery and execution framework
  * testrunner.py - TestRunner class (local/remote execution)
  * utils.py - Logging and utility functions
* e11/e11admin/ - Staff administration CLI tool
* e11/lab_tests/ - Lab test definitions (lab0-lab8)

Various directories are created:

* dist/ - The whl file that installs the e11 command

# The `e11` command
CSCI E-11 uses the `e11` command to let students control access to their AWS Instance.

The command implements these subcommands:

## The primary `e11` commands
* `e11 config` - Used to edit the configuration variables stored in `/home/ubuntu/e11-config.ini`
* `e11 register` - Registers your instance with the CSCI E-11 infrastructure, which sets up your DNS.
* `e11 status` - Status report
* `e11 version` - Show version information for both local and server
* `e11 update` - Update the e11 system
* `e11 doctor` - Run system diagnostics

## The `e11 access` subcommand
* `e11 access on` - Allows the class staff to `ssh` into your instance. This is required for grading and is the default mode.
* `e11 access off` - Disables access to your instance. Your instance lab cannot be graded if access is off.
* `e11 access check` - Reports if access is enabled or disabled.
* `e11 access check-dashboard` - Check SSH access status from the dashboard for authenticated users

## The `e11 check` subcommand
* `e11 check [lab1|lab2|lab3|lab4|lab5|lab6|lab7|lab8]` - Runs the lab checker for each lab. Not every aspect of the lab is checked, but many are.

## The `e11 grade` subcommand
* `e11 grade [lab]` - Request lab grading (typically run from course server)
* `e11 grade [lab] --direct` - Grade directly from this system (requires SSH access to target)
* `e11 grade [lab] --verbose` - Print all grading details

## The `e11 answer` subcommand
* `e11 answer [lab]` - Answer additional questions for a particular lab prior to grading (e.g., API keys for lab4, lab5, lab6)

## The `e11 report` subcommand
* `e11 report tests` - List all available tests in markdown format

## The `e11 lab8` subcommand
* `e11 lab8 --upload [file]` - Upload a file for lab8

## Global Options

These options must be placed **before** the subcommand:
* `e11 --debug <command>` - Run in debug mode
* `e11 --stage <command>` - Use stage API instead of production
* `e11 --force <command>` - Run even if not on EC2 (useful for local testing)
* `e11 --keyfile <path> <command>` - Specify SSH private key file for grading

Example: `e11 --force doctor` (not `e11 doctor --force`)

## Staff Commands

### Staff Commands in `e11` (requires `E11_STAFF` environment variable)
When the `E11_STAFF` environment variable is set, additional staff-only commands are available.

**Staff commands require AWS credentials:**
```bash
E11_STAFF=1 AWS_REGION=us-east-1 AWS_PROFILE=e11-staff poetry run e11 <command>
```

Available staff commands:
* `e11 check-access <host>` - Check SSH accessibility to a student's VM
* `e11 register-email <email>` - Register an email address directly with DynamoDB
* `e11 student-report` - Generate user report from DynamoDB (shows table stats and registered users)
* `e11 student-report --dump` - Dump all user information
* `e11 grades <email>` - Show all grades for a specific student
* `e11 grades <lab>` - Show all grades for a specific lab (e.g., `e11 grades lab1`)

### The `e11admin` Command
The `e11admin` command is a separate CLI tool for faculty to run on their desktop computers.
It is installed alongside the `e11` command when you install the e11 package.

**Running e11admin requires AWS SSO authentication:**

1. First, authenticate with AWS SSO:
```bash
AWS_REGION=us-east-2 AWS_PROFILE=e11-staff aws sso login
```

2. Navigate to the e11-cli directory and install dependencies:
```bash
cd etc/e11-cli
poetry install
```

3. Run e11admin with the required environment variables:
```bash
E11_STAFF=1 AWS_REGION=us-east-1 AWS_PROFILE=e11-staff poetry run e11admin
```

| Variable | Description |
|----------|-------------|
| `E11_STAFF=1` | Enables staff-only commands |
| `AWS_REGION=us-east-1` | AWS region where DynamoDB tables are located |
| `AWS_PROFILE=e11-staff` | AWS CLI profile configured for SSO |

**Notes:**
- The `e11-staff` AWS profile must be configured in `~/.aws/config` for SSO access
- SSO login uses `us-east-2`, but DynamoDB operations use `us-east-1`
- Running `e11admin` without arguments displays all registered users and DynamoDB tables
- Python 3.12-3.13 required (3.14 not supported)

Options:
* `--dump` - Dump all table data
* `--delete_userid <id>` - Delete a user by user_id
* `--delete_item` - Delete a specific item (requires --user_id and --sk)
* `--newkey <email>` - Create a new course key for a user
* `--user_id <id>` - Specify user_id for operations
* `--sk <key>` - Specify sort key for operations
* `--ssh <email>` - SSH into a student's VM

See `e11/e11admin/README.md` for details.

# DynamoDB Database Structure

The E11 system uses four DynamoDB tables:

## e11-users Table
The main table storing user records, grades, logs, and images.

| Attribute | Description |
|-----------|-------------|
| `user_id` (PK) | Partition key - UUID for each user |
| `sk` (SK) | Sort key - determines record type |
| `email` | Student email address (GSI) |

### Sort Key Patterns
| Pattern | Description |
|---------|-------------|
| `#` | User record (main profile) |
| `grade#<lab>#<timestamp>` | Grade records for lab submissions |
| `log#<timestamp>` | User activity log entries |
| `image#<lab>#<timestamp>` | Lab 8 image upload records |
| `leaderboard-log#<timestamp>` | Leaderboard activity records |

### Global Secondary Index
* **GSI_Email** - Partition key: `email`, Projection: ALL

## home-app-sessions Tables
Session management for the web dashboard. Table names vary by environment:
* `home-app-prod-sessions` - Production
* `home-app-stage-sessions` - Staging

| Attribute | Description |
|-----------|-------------|
| `sid` (PK) | Session ID (UUID) |
| `email` | User email (GSI) |
| `session_created` | Creation timestamp |
| `session_expire` | Expiration timestamp |

## Leaderboard Table
Stores Lab 7 leaderboard entries.

| Attribute | Description |
|-----------|-------------|
| `name` (PK) | Unique leader name |
| `first_seen` | When first added |
| `last_seen` | Last activity timestamp |
| `score` | Leaderboard score |

# Safe CLI Commands for Development

The following commands are read-only and safe for testing:

```bash
# Help and documentation
e11 --help                    # Show all commands
e11 <command> --help          # Show help for specific command

# Status and diagnostics
e11 version                   # Show local and server version
e11 status                    # Display configuration state
e11 doctor                    # Run system diagnostics

# Reports
e11 report tests              # List all available tests (markdown)

# Access checking (informational only)
e11 access check              # Check if SSH access is enabled
```

# Development Workflow

For detailed architecture documentation, see [ARCHITECTURE.md](ARCHITECTURE.md).

## Prerequisites
* Python 3.12+ (CLI) / Python 3.13 (Lambda)
* Poetry (dependency management)
* AWS SAM CLI (for Lambda deployment)

## Setting Up Development Environment

```bash
cd etc/e11-cli
poetry install --with dev
poetry run e11 --help
```

## Building and Testing

```bash
# Run tests with coverage
make check

# Run linting (pylint + pyright)
make lint

# Test all components (CLI + both Lambdas)
make check-all
```

## Vendored Wheel Pattern

**IMPORTANT**: The `e11/` package is built into a wheel and vendored into Lambda functions:
* `lambda-home/src/home_app/e11.whl`
* `lambda-leaderboard/src/leaderboard_app/e11.whl`

After modifying `e11/` or `e11core/`:
```bash
poetry build
cd lambda-home && make vend-e11
cd ../lambda-leaderboard && make vend-e11
```

## Local DynamoDB Testing

```bash
make start_local_dynamodb     # Start DynamoDB Local
make stop_local_dynamodb      # Stop DynamoDB Local
```

# How it Works

This program can be found on [GitHub in the spring26 repo](https://github.com/Harvard-CSCI-E-11/spring26/tree/main/etc/e11-cli). The repo is checked out by the student and then installed in `$HOME/.local/bin` using `pipx` by the [install-e11](https://github.com/Harvard-CSCI-E-11/spring26/blob/main/etc/install-e11) installation script.

## Running from this repo

```bash
poetry sync
poetry run e11
```

## Package Entry Points

The package defines two CLI entry points in `pyproject.toml`:
* `e11` - Main student CLI command
* `e11admin` - Staff administration CLI command

## Related Documentation
* [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system architecture and data flows
* [TESTING_STRATEGY.md](TESTING_STRATEGY.md) - Testing approach and patterns
* [e11/e11admin/README.md](e11/e11admin/README.md) - Admin CLI documentation
