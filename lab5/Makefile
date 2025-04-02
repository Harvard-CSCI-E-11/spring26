#
# This is a Unix Makefile for Lab 5
#

################################################################
# Installation targets
#
# Create the virtual environment
venv:
	make venv/pyvenv.cfg

venv/pyvenv.cfg:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	venv/bin/python3 -m pip install --upgrade pip
	venv/bin/python3 -m pip install -r requirements.txt

#
# Install the lab5.services file
install-lab5-service: venv/pyvenv.cfg
	sudo install lab5.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab5
	sudo systemctl start lab5
	@# Do not overwrite lab5 as it may have been customized
	@if [ ! -r /etc/httpd/conf.d/lab5.conf ]; \
		then echo installing /etc/httpd/conf.d/lab5.conf ; \
		sudo install lab5.conf /etc/httpd/conf.d/ ; \
		else echo /etc/httpd/conf.d/lab5.conf already installed ; \
	fi
	@echo
	@echo Do not forget to edit ServerName in /etc/httpd/conf.d/lab5.conf, restart apache, and run certbot, and restart apache again
	@echo You may also need to restart your web browser.

################################################################
# Application targets
# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
.PHONY: local-app
local-app:
	venv/bin/flask --app app run --debug

# Print help for the application
.PHONY: help
help:
	venv/bin/flask --app app --help

# Create a new database
instance/server_db.sqlite:
	venv/bin/flask --app app init-db

# Create the s3 bucket and establish the CORS policy
.PHONY: init-s3
init-s3:
	venv/bin/flask --app app init-s3

.PHONY: init-db
init-db:
	venv/bin/flask --app app init-db

# Generate a new api-key
.PHONY: new-apikey
new-apikey: instance/server_db.sqlite
	venv/bin/flask --app app new-apikey

# Dump the database
.PHONY: dump-db
dump-db: instance/server_db.sqlite
	venv/bin/flask --app app dump-db


#
# Software engineering targets

pylint:
	venv/bin/python3 -m pylint app


################################################################
## Healthcheck - before you start lab3

.PHONY: healthcheck
healthcheck:
	python3 -m healthcheck.main

pylint-healthcheck:
	venv/bin/python3 -m pylint  --rcfile=healthcheck/.pylintrc healthcheck

# make venv always run, even if it exists
.PHONY: venv
.PHONY: install-lab5-service
