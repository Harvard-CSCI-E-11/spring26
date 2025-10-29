Changes from last year:
=======================
* We moved from AWS Linux to Ubuntu 24.04 Linux. We did this because there are more online tutorials for Ubuntu Linux than for AWS Linux, and because Ubuntu Linux is available on more platforms (e.g. Raspberry PI or [MacOS](https://dev.to/ryfazrin/how-to-run-ubuntu-on-macos-like-wsl-wsl-style-experience-4cd4)).
* We have a script [etc/install-e11](../etc/install-e11) that configures Ubuntu 24.04 for the class
* We created a new command, `e11`, for course VM management.
* We now use [`pipx`](https://pipx.pypa.io/latest/) to manage python commands in the CLI (including e11)
* The old lab2 (a library-based assigment) was removed.
* The old [lab3](https://github.com/Harvard-CSCI-E-11/spring25/tree/main/lab3) which involved standing up a database-driven website with a SQL injection vulnerability was changed into two labs:
  - [lab2](lab2/) [A web server with password-based access control](https://docs.google.com/document/d/1-3Wrh1coGqYvgfIbGvei8lw3XJQod85zzuvfdMStsvs/edit?tab=t.0)
  - [lab3](lab3/) [A simple database-driven web app written in python](https://docs.google.com/document/d/1pOeS03gJRGaUTezjs4-K6loY3SoVx4xRYk6Prj7WClU/edit?tab=t.0)
* The old [lab5](https://github.com/Harvard-CSCI-E-11/spring25/tree/main/lab5) which involved creating a system that allowed uploading images and then feeding them through Amazon Rekognition has been split into two labs:
  - [lab5](lab5/) [Add images to your message board](https://docs.google.com/document/d/1CW48xvpbEE9xPs_6_2cQjOQ4A7xvWgoWCEMgkPjNDuc/edit?usp=drive_web&ouid=114142951656037982317)
  - [lab6](lab6/) [AI image analysis with AWS Rekognition](https://docs.google.com/document/d/1aRFFRaWmMrmgn3ONQDGhYghC-823GbGzAP-7qdt5E0U/edit?tab=t.0)
