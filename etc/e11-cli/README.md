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

## The `e11 access` subcommand
* `e11 access on` - Allows the class staff to `ssh` into your instance. This is required for grading and is the default mode.
* `e11 access off` - Disables access to your instance. Your instance lab cannot be graded if access is off.
* `e11 access check` - Reports if access is enabled or disabled.

## The `e11 check` subcommand
* `e11 check [lab1|lab2|lab3|lab4|lab5]` - Runs the lab checker for each lab. Not every aspect of the lab is checked, but many are.

# How it works
This program can be found on [GitHub in the spring26 repo](https://github.com/Harvard-CSCI-E-11/spring26/tree/main/etc/e11). The repo is checked out by the student and then installed in `$HOME/.local/bin` using `pipx` by the [install-e11](https://github.com/Harvard-CSCI-E-11/spring26/blob/main/etc/install-e11) installation script.

You can run out of this repo with these commands:
```
$ poetry sync
$ poetry run e11
```
