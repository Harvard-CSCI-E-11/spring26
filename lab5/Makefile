#
# This is a Unix Makefile for Lab 5
#

################################################################
# Installation targets
#
# Create the virtual environment
venv:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	. venv/bin/activate ; python3 -m pip install --upgrade pip
	. venv/bin/activate ; python3 -m pip install -r requirements.txt

#
# Install the lab5.services file
install-lab5-service:
	sudo install lab5.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab5
	sudo systemctl start lab5
	@# Do not overwrite lab5 as it may have been customized
	@if [ ! -r /etc/httpd/conf.d/lab5.conf ]; \
		then echo installing /etc/httpd/conf/lab5.conf ; \
		sudo install lab5.conf /etc/httpd/conf.d/ ; \
		else echo /etc/httpd/conf/lab5.conf already installed ; \
	fi
	echo do not forget to edit /etc/httpd/conf/lab5.conf

################################################################
# Application targets
# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
local-app:
	. venv/bin/activate; flask --app app run --debug

# Print help for the application
help:
	. venv/bin/activate; flask --app app --help

# Create a new database
init-db:
	. venv/bin/activate; flask --app app init-db
# Generate a new api-key
new-apikey:
	. venv/bin/activate; flask --app app new-apikey

# Dump the database
dump-db:
	. venv/bin/activate; flask --app app dump-db


#
# Software engineering targets

pylint:
	. venv/bin/activate; python3 -m pylint app



# make venv always run, even if it exists
.PHONY: venv
.PHONY: install-lab5-service
