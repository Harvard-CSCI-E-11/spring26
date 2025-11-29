# Lab Tests Directory

## Purpose

The `lab_tests/` directory contains test definitions that are executed against student virtual machines (VMs) running in AWS. These tests verify that students have correctly completed their lab assignments.

## Overview

Each lab has a corresponding test file named `labN_test.py` where N is the lab number (e.g., `lab0_test.py`, `lab1_test.py`). These test files contain functions that check various aspects of the student's work:

- Configuration correctness (e.g., API keys, environment setup)
- Service functionality (e.g., nginx, gunicorn, databases)
- File system state (e.g., expected files, directory structure)
- Network services (e.g., HTTP endpoints, DNS configuration)
- Security settings (e.g., SSH keys, file permissions)

## Test Execution Context

### Two Execution Modes

These tests are designed to run in two different contexts:

1. **Local Execution** (`e11 check labN`): When a student runs `e11 check labN` on their own VM, the tests execute locally on that VM. The `TestRunner` object uses local subprocess calls and file system access.

2. **Remote Execution** (Grading): When the course staff grades a lab via the AWS Lambda function, the tests execute remotely. The `TestRunner` object uses SSH to connect to the student's VM and executes commands and file reads over the SSH connection.

### TestRunner Interface

All test functions receive a `TestRunner` object (typically named `tr`) as their first parameter. The `TestRunner` provides a uniform interface for:

- **Command Execution**: `tr.run_command(command)` - Execute shell commands locally or remotely
- **File Reading**: `tr.read_file(path)` - Read files locally or via SFTP
- **Context Access**: `tr.ctx` - Access lab context (labdir, public_ip, email, etc.)
- **HTTP Requests**: `tr.http_get(url)` - Make HTTP requests
- **Python Execution**: `tr.python_entry(file, func, args, kwargs)` - Execute Python functions

The `TestRunner` abstracts away whether it's running locally or remotely via SSH, making the same test code work in both contexts.

## Test Function Structure

### Basic Test Function

All test functions must:

1. Accept a `TestRunner` parameter (conventionally named `tr`)
2. Be named with the prefix `test_`
3. Optionally use the `@timeout(seconds)` decorator to prevent hanging tests
4. Raise `TestFail` exception on failure, or return a string message on success

Tests follow a pattern where they use the TestRunner methods to execute commands, read files, or make HTTP requests, then use assertions or raise TestFail exceptions to indicate success or failure.

### Test Context (`tr.ctx`)

The test context provides information about the lab environment:

- `ctx.lab` - Lab name (e.g., "lab3")
- `ctx.labdir` - Full path to the lab directory (e.g., "/home/ubuntu/spring26/etc/lab3")
- `ctx.public_ip` - Public IP address of the VM (for grading)
- `ctx.email` - Student's email address
- `ctx.smashedemail` - Hashed email for DNS names
- `ctx.labdns` - DNS name for the lab (e.g., "student-lab3.csci-e-11.org")
- `ctx.course_key` - Student's course key

Tests can access and modify the context as needed (e.g., storing computed values for later tests).

### Common Test Patterns

Tests typically follow these patterns:

- **File Testing**: Use `tr.read_file()` to read files and verify their content using assertions
- **Service Testing**: Use `tr.run_command()` to check service status via system commands
- **HTTP Testing**: Use `tr.http_get()` to verify web endpoints respond correctly
- **Database Testing**: Use `tr.run_command()` with database tools to verify schema or data

Refer to existing test files for concrete examples of these patterns.

## Common Test Utilities

### `lab_common.py`

The `lab_common.py` file contains shared test functions that are used across multiple labs. These functions handle common checks like verifying SSH keys, virtual environments, service configurations, and database setup.

Individual lab test files can import and reuse these common test functions to avoid duplication.

## Test Discovery and Execution

### How Tests Are Discovered

The grader system (`e11/e11core/grader.py`) discovers tests using Python's `importlib`:

1. Given a lab name (e.g., "lab3"), it imports the module `e11.lab_tests.lab3_test`
2. It scans the module for all functions named `test_*`
3. It collects these functions in definition order (to allow dependent tests)
4. It executes each test function, passing the `TestRunner` object

### Test Execution Flow

1. **Context Building**: The `build_ctx()` function creates an `E11Context` with lab information
2. **TestRunner Creation**: A `TestRunner` is created:
   - **Local**: `TestRunner(ctx)` - uses local subprocess/file access
   - **Remote**: `TestRunner(ctx, ssh=E11Ssh(...))` - uses SSH for remote execution
3. **Test Discovery**: Functions named `test_*` are collected from the lab's test module
4. **Test Execution**: Each test runs with a timeout:
   - Success: Returns a string message (optional)
   - Failure: Raises `TestFail` exception
   - Error: Any other exception is caught and reported
5. **Results Collection**: Results are collected into a summary dictionary
6. **Score Calculation**: Score is calculated as `5.0 * (passes / total_tests)`

## Writing New Lab Tests

### Guidelines

1. **Test One Thing**: Each test should verify a single aspect of the lab
2. **Clear Failure Messages**: Use descriptive `TestFail` messages that help students understand what's wrong
3. **Provide Context**: Include relevant output (stderr, file contents) in the `context` parameter of `TestFail`
4. **Use Timeouts**: Apply `@timeout(seconds)` decorator to prevent tests from hanging
5. **Return Success Messages**: Return helpful messages on success (these are shown to students)
6. **Handle Errors Gracefully**: Catch exceptions and convert them to `TestFail` with context

### Dependencies Between Tests

Tests run in definition order. If one test sets up state used by later tests, document this clearly in the test's docstring and ensure dependent tests check for the required state before proceeding.

## Test Results and Scoring

### Test Result Structure

Each test produces a result dictionary containing the test name, status (pass/fail), message, optional context information, and execution duration.

### Score Calculation

- **Score Formula**: `5.0 * (number_of_passes / total_tests)`
- **Maximum Score**: 5.0 (all tests pass)
- **Minimum Score**: 0.0 (all tests fail)

### Output to Students

When students run `e11 check labN`, they see formatted output showing the lab name, public IP address, score, and lists of passing and failing tests with their messages and context.

## Important Notes

1. **Test Files Are Not Unit Tested**: These test files are definitions, not code to be tested. They are excluded from coverage metrics.

2. **Tests Must Work in Both Contexts**: All tests must work both locally (when student runs `e11 check`) and remotely (when grader SSHs in). Avoid assuming local-only features.

3. **Security Considerations**: Tests execute with the privileges of the user running them. Be careful with commands that modify system state.

4. **Performance**: Keep tests fast. Use appropriate timeouts and avoid long-running operations when possible.

5. **Maintainability**: Write clear, readable tests. Future course staff will need to understand and modify these tests.

## Related Documentation

The test execution framework is implemented in the `e11/e11core/` module. See the source code for:

- `grader.py` - Test discovery and execution framework
- `testrunner.py` - TestRunner class implementation
- `assertions.py` - Assertion helpers for tests
- `decorators.py` - Decorators like `@timeout` and `@retry`

Also see `TESTING.md` in the project root for general testing documentation.

