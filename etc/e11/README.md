This directory contains the following:
* e11/ - The source code for the e11 command
* grader/ - The code for the auto-grader that runs on AWS Lambda
* tests/ - tests for the e11 and grader system (because nothing should be written without a

You will also find in this directory:
* e11/e11/lab_tests - the actual tests for your labs.


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
* `ell access check` - Reports if access is enabled or disabled.

## The `e11 check` subcommand
* `e11 check [lab1|lab2|lab3|lab4|lab5]` - Runs the lab checker for each lab. Not every aspect of the lab is checked, but many are.

# How it works
This program can be found on [GitHub in the spring26 repo](https://github.com/Harvard-CSCI-E-11/spring26/tree/main/etc/e11). The repo is checked out by the student and then installed in `$HOME/.local/bin` using `pipx` by the [install-e11](https://github.com/Harvard-CSCI-E-11/spring26/blob/main/etc/install-e11) installation script.

You can run out of this repo with these commands:
```
$ poetry sync
$ poetry run e11
```
