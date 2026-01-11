This directory contains the following:
* e11/ - The source code for the e11 command
* lambda-home/ - The code for the AWS Lambda function at https://csci-e-11.org/ that runs the student dashboard and performs grading
* lambda-users-db/ - The SAM lambda for creating the users-db (it's not really a lambda)
* tests/ - tests for the e11 and grader system (because nothing should be written without a test)

You will also find in this directory:
* e11/__main__.py - The actual code for the e11 command
* e11/e11core - The code that implements core functions for the grader
* e11/e11core/assertions.py - misc asserts available for tests
* e11/e11core/config.py - E11Config object - the object that is passed to the grader functions in the context
* e11/e11core/constants.py - constants. this is where 'spring26' is defined. Not all uses are fully parameterized
* e11/e11core/context.py - builds the context that is passed. This should be folded into config.py, possibly
* e11/e11core/decorators.py - defines @timeout and @retry
* e11/e11core/e11ssh.py - ssh access to student VMs
* e11/e11core/grader.py - the grader framework including renderers for print and email the grading summary
* e11/e11core/testrunner.py - Defines the testrunner class, which actually runs all of the tests in each test program
* e11/e11core/utils.py - various utilities. Merge with constants.py into common.py?
* e11/lab_tests - the actual tests for your labs.

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

## Staff Commands

### Staff Commands in `e11` (requires `E11_STAFF` environment variable)
When the `E11_STAFF` environment variable is set, additional staff-only commands are available:
* `e11 check-access [host]` - Check to see if we can access a host
* `e11 register-email [email]` - Register an email address directly with DynamoDB
* `e11 student-report [--dump]` - Generate a report directly from DynamoDB
* `e11 grades [email|lab]` - Show grades for a student or a lab

### The `e11admin` Command
The `e11admin` command is a separate CLI tool for faculty to run on their desktop computers.
It is installed alongside the `e11` command when you install the e11 package. See `e11/e11admin/README.md` for details.

# How it works
This program can be found on [GitHub in the spring26 repo](https://github.com/Harvard-CSCI-E-11/spring26/tree/main/etc/e11). The repo is checked out by the student and then installed in `$HOME/.local/bin` using `pipx` by the [install-e11](https://github.com/Harvard-CSCI-E-11/spring26/blob/main/etc/install-e11) installation script.

You can run out of this repo with these commands:
```
$ poetry sync
$ poetry run e11
```
