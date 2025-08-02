# CSCI E-11 git repo

This is the CSCI E-11 git repo for the Spring of 2026. It contains sample code, templates, and the text of the labs themselves.

To use this repo, log into your AWS instance and type these commands at the `$` prompt (you do not type the prompt below):
```
$ sudo apt install git
$ git checkout https://Harvard-CSCI-E-11/spring26.git
$ spring26/etc/install-e11
```

The student labs are identified:

|Lab |Due |Content  |Security Topcics|
|----|----|---------|----------------|
| [lab1](lab1/) | | Create an instance and monitor for attacks | Basic command line, SSH,  and Log analysis|
| [lab2](lab2/) | | Stand up a web server that serves three static pages | TLS certificates|
| [lab3](lab3/) | | Add a database-driven message board to your website. | SQL injection attacks|
| [lab4](lab4/) | | Add images to your message board. | AWS signed HTTP POSTs and URLs.|
| [lab5](lab5/) | | AI image analysis with AWS Rekognition| Face detection and matching |
| [lab6](lab6/) | | Accessing the leaderboard from a microcontroler | Introduction to CircuitPython.|
| [lab5](lab7/) | | Uploading images from the edge | AI, Internet of Things, and Cybersecurity|


The staff/ directory is for use by the course staff. It's how we make things work! Students are welcome to look through it and ask questions of the teaching staff.

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
