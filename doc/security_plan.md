|                               |                                                              |
| :---------------------------- | ------------------------------------------------------------ |
| Course Name                   | Artificial Intelligence, Internet of Things, and Cybersecurity |
| Course Number                 | CSCI E-11                                                    |
| Semester                      | Spring 2026                                                  |
| Instructors                   | Geoff Cohen & Simson Garfinkel                               |
| Courseware Security Architect | Simson Garfinkel                                             |



CSCI E-11 Courseware Security Plan
======================

The CSCI E-11 labs require students to create and manage virtual machine instances in the Amazon Web Services (AWS) cloud, and to deploy applications onto those instances. To improve the student experience and simplify grading, we have created a courseware package that performs the following tasks:

* Users register with the system using OIDC. Currently only Harvard Key is supported, although there are plans to add support for login with Google and GitHub.
* Performs initial configuration of the student's instance, registers the student instance with the courseware system, and creates DNS names for the student's instance in the csci-e-11.org domain. (Required so that the students can obtain Let's Encrypt TLS certificates.)
* Providers starter code for all of the labs.
* Provides a mechanism so that instructors can log into the student instance for troubling shooting, and gives the student the ability to enable or disable access.
* Provides a "check" command so that the students can diagnose potential problems with their instances  and determine if they have completed the assignment.
* Grades the student assignment to determine if the instance meets all of the requirements.
* Creates a grade sheet of all student grades that can be uploaded to Canvas


System Elements
---------------

The CSCI E-11 courseware consists of:

* The https://github.com/Harvard-CSCI-E-11/spring26 github repo which stores all software and configuration information.

* The `e11` Python module which is installed as the `e11` command on the student's instance using the `pipx` command.

* The https://csci-e-11.org/ website, which is hosted in AWS Lambda under an AWS account that has been created specifically for this course.

* Three DynamoDB tables that can only read or written by the course account.


### DynamoDB Tables

The following tables are in use:

| Name         | FERPA Data?                                                 | Access                                       | Purpose                                                      |
| ------------ | ----------------------------------------------------------- | -------------------------------------------- | ------------------------------------------------------------ |
| e11-users    | Yes                                                         | Lambda at https://csci-e-11.org/             | Stores OIDC `claims` for each user, user provided information, results of instance grading, and logs of user interaction with the website. |
| e11-sessions | No, but contains authenticators that can access FERPA data. | Lambda at https://csci-e-11.org/             | Stores active sessions (`sid`) and mapping to `email`.       |
| Leaderboard  | No                                                          | Lambda at https://leaderboard.csci-e-11.org/ | Operates the leaderboard used in lab6.                       |

All access to the tables is moderated through python functions running in AWS Lambda.

### Implementation Languages
All code is implemented in Python.

* The student VMs run Ubuntu 24.04 LTS with a default python install of Python 3.12, so we use Python 3.12 on the student VMs.

* The AWS Lambda uses Python 3.13.

Because two versions of python are used, the `e11` module is tested with both Python 3.12 and Python 3.13 as part of the unit tests.

### Code Quality

Because all access to sensitive data is moderated through python functions running in AWS Lambda, we need to be sure that the code is of high quality. The following measures are used:

* All code that has access to FERPA data is tested with unit tests.

* All unit tests are run automatically on GitHub using GitHub actions on every commit.

* Code coverage is tracked using `pytest-cov` and reported at the end of each test. Results are archived at https://app.codecov.io/github/Harvard-CSCI-E-11/spring26.


Security Model
--------------
The basic security model is:

1. All users are authenticated using Harvard Key. The claims returned by Harvard Key are stored in the `e11-users` table. Currently the only information returned by Harvard is the user's name, email address, and user identifier. The HUID, enrollment, or school/college is not collected or stored.

2. Each user is assigned a unique `user_id` that is a `uuid4`. This is the sole database key and is used as the partition key for the DynamoDB `e11-users` table. This has the effect of localizing student data to each student. Records can only be retrieved by `user_id` or by email address. The DynamoDB `scan` primitive is disallowed.

3. When a user is authenticated, a cookie is stored on the user's browser with a unique session id (`sid`) and a signature generated with the `itsdangerous` python module. The only information in the cookie is the `sid` and the signature. The sessions table contains the email address, which is then searched for in the `e11-users` table to get the user record.

4. The dashboard will only display to a user with a cookie that has a valid signature and for which the `sid` is stored in the `e11-sessions` table.  The dashboard displays a list of all active sessions and allows any to be deleted. There is also a logout button that allows the student to log out (which destroys the current session).

5. The dashboard displays all of the user's log, which includes each time the dashboard was accessed and the results of each grade run.


FERPA-protected student data is stored solely in the e11-users table.

Grading
-------
Student instances are "graded" by software that runs on Lambda that logs into the student instance and checks various configuration details. The grading functions can be viewed at https://github.com/Harvard-CSCI-E-11/spring26/tree/main/etc/e11-cli/e11/lab_tests

When the grader runs, the results are stored in the table `e11-users` with a primary key of the `user_id` and a sort key of `grade#{timestamp}`.

Faculty Access to FERPA-protected data
--------------------------------------
Faculty can access FERPA-protected data solely through the AWS console (by using the DynamoDB table inspector) and from the faculty member's laptop (by running Python commands that can access the DynamoDB table directly). This presents the same security risk as having the faculty member access Canvas from their laptop.

Data Durability
---------------
The DynamoDB tables are backed up by Amazon and have deletion protection enabled.

Data Destruction
----------------
At the end of the semester, the DynamoDB tables will be deleted.
