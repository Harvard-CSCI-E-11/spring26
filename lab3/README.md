CSCI E-11 Lab #3 - A simple database-driven web app written in python
---------------------------------------------------------------------

This lab requires students to:

- [ ] Set up nginx so that requests to smashedemail-lab3.csci-e-11.org are proxied to 127.0.0.1:8003
- [ ] Set up /etc/systemd/system/lab3.service so that gunicorn runs a flask application. Initially it is `simple_flask_application:app`
- [ ] Modify /etc/systemd/system/lab3.service so that gunicorn runs the flask application `student_server:app`
- [ ] Modify `student_server:app` so that it no longer has an SQL-injection vulnerability.
