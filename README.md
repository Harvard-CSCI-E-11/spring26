# CSCI E-11 git repo
[![CI (pip)](https://github.com/Harvard-CSCI-E-11/spring26/actions/workflows/ci-e11.yml/badge.svg)]([https://github.com/Plant-Tracer/webapp/actions/workflows/continuous-integration-pip.yml](https://github.com/Harvard-CSCI-E-11/spring26/actions/workflows/ci.yml))
[![codecov](https://codecov.io/github/Harvard-CSCI-E-11/spring26/graph/badge.svg?token=GI7Z8W3YC5)](https://codecov.io/github/Harvard-CSCI-E-11/spring26)

This is the CSCI E-11 git repo for the Spring of 2026. It contains sample code, templates, and the text of the labs themselves.

You will find the lab writeups on our [Google Drive](https://drive.google.com/drive/folders/1BexB_lGIw93CP4c6JPEMELY2m6h_qdvr).

Currently these labs require that you have a [Harvard Key](https://key.harvard.edu/) account. By January 2026, you will also be able to use them with a Google Account.

To use this repo, log into your AWS instance and type these commands at the `$` prompt (you do not type the prompt below):
```
$ sudo apt install git
$ git checkout https://Harvard-CSCI-E-11/spring26.git
$ spring26/etc/install-e11
```

The student labs are identified:

|Lab |Due |Description | E-11 Topics  |
|----|----|---------|------------|
| [lab0](lab0/) |Feb  2 | [Order your microcontroller for lab7 and lab 8](https://csci-e-11.org/lab0) | Preparation |
| [lab1](lab1/) |Feb  9 | [Create an AWS EC2 instance and monitor for attacks](https://csci-e-11.org/lab1) |  Basic command line, SSH,  and Log analysis |
| [lab2](lab2/) |Feb 16 | [A web server with password-based access control](https://csci-e-11.org/lab2) |  TLS certificates and username/password access  |
| [lab3](lab3/) |Feb 23 | [A simple database-driven web app written in python](https://csci-e-11.org/lab3) |  gunicorn, flask, and SQL injection attacks|
| [lab4](lab4/) |Mar  9 | [An API server with password hashing](https://csci-e-11.org/lab4) |  password hashing|
| [lab5](lab5/) |Mar 30 | [Add images to your message board](https://csci-e-11.org/lab5) | AWS signed HTTP POSTs and URLs.|
| [lab6](lab6/) |Apr 13 | [AI image analysis with AWS Rekognition](https://csci-e-11.org/lab6) | Face detection and face matching  |
| [lab7](lab7_memento/) <br> [lab7_linux](lab7_linux) | Apr 27 | [Calling APIs from a microcontroler](https://csci-e-11.org/lab7) <br> (Client code that runs on Linux) |  Introduction to IoT CircuitPython.|
| [lab8](lab8_memento/) <br> [lab8_linux)(lab8_linux) <br> [lab8](lab8/)| May 11| [Uploading images from the edge](https://csci-e-11.org/lab8) <br> (Client code that runs on Linux) <br> (Empty directory for lab8 server) |  AI, Internet of Things, and Cybersecurity|

This table describes each lab and the services used:

| Lab | DNS domain                      | Web Server | Application Server | API Key Prefix | AWS Technologies |
|-----|---------------------------------|------------|--------------------|----------------|-----------|
|lab1 | smashedemail.csci-e-11.org      | --         | --                 | --             | EC2|
|lab2 | smashedemail.csci-e-11.org      | nginx      | --                 | --             | EC2|
|lab3 | smashedemail-lab3.csci-e-11.org | nginx      | flask              | `lab3:`        | EC2|
|lab4 | smashedemail-lab4.csci-e-11.org | nginx      | flask              | `lab4:`        | EC2|
|lab5 | smashedemail-lab5.csci-e-11.org | nginx      | flask              | `lab5:`        | EC2, S3|
|lab6 | smashedemail-lab6.csci-e-11.org | nginx      | flask              | `lab6:`        | EC2, S3, Rekognition|
|lab7 | --                              | --         | --                 | --             | DynamoDB, Lambda _(see Note1)_ |
|lab8 | smashedemail-lab8.csci-e-11.org | nginx      | flask              | `lab8:` _(See Note2)_       | EC2, S3, Rekognition|

_Note1: on the backend, we implement lab7 with AWS DynamoDB and Lambda._

_Note2: For lab8, students set up all of the files for themselves, using lab6 as the prototype. The easy way to do this is to copy the lab6 directory into lab8 and change `lab6` to `lab8` in the various files as necessary.

_Note3:_ The lab4, lab5, lab6 and lab8 all build on a common application. The common files are in the [lab_common](lab_common/) directory, with symbolic links to the files located in lab[456] directories. You do not need to modify these files to complete the assignments. The files that are customized for each lab are present in the lab[456] directories.

The [staff/](staff/) directory is for use by the course staff. It's how we make things work! Students are welcome to look through it and ask questions of the teaching staff.

The [etc/](etc/) directory contains the source code for the `e11` command, the portions of the `e11` system that run on AWS Lambda, and the [e11 installer script](etc/install-e11).

# Python quick-start
This course assumes that you have had some introduction to the Python programming language.

We will make use of the following Python technologies. Please follow the links for documentation if you are unsur:
* [Python virtual environments](https://docs.python.org/3/library/venv.html) (e.g. venv)
* [Poetry](https://python-poetry.org/) to manage python virtual environments and packaging


# Amazon Web Services (AWS) quick-start
This course does not assume that you know how to use Amazon Web Services, but it does assume you will read all of the documentation before asking questions.

* We ask that you create a new AWS account specificly for this course.
* You will create a Linux "instance" in Amazon's [Elastic Compute Cloud (EC2)](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/concepts.html)
  * You should create an [EC2 instance type](https://aws.amazon.com/ec2/instance-types/) that qualifies for the AWS "free tier."
  * You will get a warning at the end of each month that you have nearly used up your 750 hours of free tier usage for the month.
  * As there are only 744 hours in months with 31 days, this will not result in a charge unless you have created additional instances, or if your instance is not at the free tier.
* You will be using Ubuntu Linux 24.04 LTS from the command line.
* You will edit files with either the emacs, vi or nano editors.

AWS Permissions:
* You will create an AWS Security Role called `EC2_Class_Role`  and assing it to your instance.
* The `EC2_Class_Role` will eventually have three attached permission policies:
  * `AmazonEC2ReadOnlyAccess`  (added in Lab 1)
  * `AWSAccountManagementReadOnlyAccess`  (added in Lab 1)
  * `AmazonS3FullAccess` (added in Lab 5)
