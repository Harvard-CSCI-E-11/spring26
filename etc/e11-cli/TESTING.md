# Testing Documentation for E11 CLI and Lambda-Home

This document describes the testing strategy, tools, and processes for the E11 CLI and Lambda-Home projects.

## Overview

The E11 project consists of two main components that are tested independently:

1. **E11 CLI** (`e11/`) - The command-line interface installed on student VMs via `pipx`
2. **Lambda-Home** (`lambda-home/`) - The AWS Lambda function that powers the student dashboard at https://csci-e-11.org/

Both components share the `e11` Python module, but they are tested independently as separate test suites.

## Test Execution

### Running Tests Locally

#### E11 CLI Tests
```bash
# From the project root
make check
```

This will:
- Run pylint on the e11 module
- Run pytest with coverage on `tests/`
- Generate coverage reports (terminal and XML)

#### Lambda-Home Tests
```bash
# From the lambda-home directory
cd lambda-home
make check
```

This will:
- Vendor the e11 module as a wheel
- Run linting (djlint, ruff, pylint, pyright)
- Run pytest with coverage on `tests/`
- Generate coverage reports (terminal and XML)
- Validate SAM templates

### CI/CD Integration

All tests run automatically in CI/CD pipelines. Both test suites must pass before code can be merged.

### Pre-Deployment Requirements

**Critical**: Before deploying lambda-home to either production or staging, the following must pass:

1. **Full static analysis**:
   - `pylint` on all source code
   - `pyright` type checking
   - `ruff` linting and formatting checks
   - `djlint` template linting (for Jinja2 templates)
   - SAM template validation

2. **All tests must pass**:
   - All unit tests
   - All integration tests
   - Coverage thresholds must be met

This is enforced by the Makefile targets (`make check` and `make lint`). The deployment targets (`make prod-vbd` and `make stage-vbd`) will automatically run these checks before deploying.

**Rationale**: The reliability of the system for students depends on extensive testing and thorough static analysis. We prioritize catching errors before deployment rather than in production.

## Testing Philosophy

### Principles

1. **No Monkeypatching**: We avoid monkeypatching whenever possible. Instead, we use:
   - Real filesystem operations in temporary directories
   - Real HTTP requests to test servers (pytest-httpserver)
   - Real subprocess calls with controlled inputs
   - Environment isolation through pytest fixtures

2. **Minimal Code Duplication**: Shared testing utilities are located in:
   - `tests/shared_fixtures/` - Common fixtures for both test suites
   - `tests/shared_helpers/` - Shared assertion helpers and data factories

3. **Test Real Behavior**: Tests should exercise actual functionality, not mocked interfaces. This makes tests more reliable and easier to understand.

### Excluded from Testing

1. **SSH Functionality**: Functions that require SSH connections are not currently tested. This includes:
   - `E11Ssh` class methods (except basic initialization)
   - Remote command execution via SSH
   - SFTP operations
   - Staff commands that require SSH access

2. **Lab Tests**: The `e11/lab_tests/*.py` files are test definitions, not code to be tested. These are integration tests that run against student VMs. See `e11/lab_tests/README.md` for details.

3. **External Services**: Some AWS service interactions are tested using `moto` or skipped entirely:
   - DynamoDB operations are tested using `moto` (in-memory DynamoDB)
   - Future work may use DynamoDBLocal for more accurate testing
   - Route53 operations are tested using `moto`

## Test Structure

Tests are organized into separate directories for the E11 CLI and Lambda-Home components. Each test suite includes:

- Configuration files (`conftest.py`) for pytest fixtures
- Test files covering different aspects of the functionality
- Test data files as needed
- Shared utilities and fixtures to avoid code duplication

See the actual test directories for the current structure.

## Coverage Goals

### Current Coverage

- **E11 CLI**: 32.79% (507/1546 lines)
- **Lambda-Home**: 70.8% (902/1274 lines)

### Target Coverage

- **E11 CLI**: 70%+ (focus on critical paths: commands, error handling, core functionality)
- **Lambda-Home**: 85%+ (focus on error paths, edge cases, authentication flows)

### Coverage Priorities

1. **Critical Paths**: Commands that students use daily (register, config, check)
2. **Error Handling**: All exception handlers and error paths
3. **Authentication & Security**: OIDC flows, session management, access control
4. **Core Functionality**: Grader framework, test runner, context building

### Excluded from Coverage

- SSH-related functionality (as noted above)
- Lab test definitions (`lab_tests/*.py`)
- Code that requires external services we cannot easily test

## Static Analysis Tools

### Pylint

Configuration: `.pylintrc` (if present) or default settings

Run manually:
```bash
poetry run pylint e11/
poetry run pylint lambda-home/src
```

### Pyright

Type checking for Python code. Configured via `pyproject.toml` or `pyrightconfig.json`.

Run manually:
```bash
poetry run pyright
```

### Ruff

Fast Python linter and formatter. Configuration in `pyproject.toml`.

Run manually:
```bash
poetry run ruff check --fix
poetry run ruff format
```

### djlint

Linter for Jinja2 templates (HTML templates in lambda-home).

Run manually:
```bash
poetry run djlint --profile=jinja --lint lambda-home/src/home_app/templates/
```

## Test Fixtures and Utilities

### Common Fixtures (in `tests/shared/`)

- **Config Fixtures**: Create test configuration files
- **Filesystem Fixtures**: Temporary directories and files
- **HTTP Fixtures**: Test HTTP servers for API testing
- **AWS Fixtures**: Mock AWS services (DynamoDB, Route53, SES, Secrets Manager)

### Dependency Injection Pattern

Instead of monkeypatching, we use dependency injection by designing functions to accept their dependencies as parameters rather than accessing global state. This makes testing easier and code more maintainable.

## Future Testing Improvements

1. **DynamoDBLocal Integration**: Use Amazon's DynamoDBLocal.jar for more accurate DynamoDB testing
2. **SSH Testing**: Add SSH testing capabilities using test containers or mock SSH servers
3. **Integration Tests**: Add more end-to-end integration tests that exercise the full system
4. **Performance Tests**: Add tests for performance-critical paths
5. **Security Tests**: Add tests for security-sensitive operations

## Debugging Tests

### Running Individual Tests

```bash
# E11 CLI
poetry run pytest tests/test_specific.py::test_function -v

# Lambda-Home
cd lambda-home
poetry run pytest tests/test_specific.py::test_function -v
```

### Coverage Reports

Coverage reports are generated in multiple formats:

- **Terminal**: Summary shown during test run
- **XML**: `coverage.xml` (for CI/CD integration)
- **HTML**: Generated with `coverage html` (not in default Makefile targets)

View HTML coverage:
```bash
coverage html
open htmlcov/index.html  # or browse to htmlcov/index.html
```

### Verbose Output

```bash
# E11 CLI
poetry run pytest tests/ -v --log-cli-level=DEBUG

# Lambda-Home
cd lambda-home
poetry run pytest tests/ -v --log-cli-level=DEBUG
```

## Best Practices

1. **Write Tests First**: When adding new functionality, write tests first (TDD approach)
2. **Test Error Cases**: Always test error paths, not just happy paths
3. **Use Fixtures**: Leverage pytest fixtures to avoid code duplication
4. **Clear Test Names**: Test function names should clearly describe what they test
5. **Isolated Tests**: Tests should not depend on each other or external state
6. **Fast Tests**: Keep unit tests fast; use integration tests for slower operations
7. **Maintainable Tests**: Tests should be easy to understand and modify

## Troubleshooting

### Tests Fail Locally But Pass in CI

- Check Python version (CI uses specific versions)
- Check environment variables
- Check for file system permissions
- Ensure all dependencies are installed

### Coverage Not Increasing

- Check that new code is actually being executed
- Verify that test files are being discovered by pytest
- Check that coverage configuration includes the right paths

### Static Analysis Failures

- Review the specific linter errors
- Fix errors locally before committing
- Use `--fix` flags where available (ruff, djlint)
- Document any necessary suppressions (pylint disable comments)

