#
# This is a Unix Makefile for Lab 4
#
# The best Makefile tutorial we have found is here:
# https://opensource.com/article/18/8/what-how-makefile
#
# For background, see:
# https://en.wikipedia.org/wiki/Make_(software)

################################################################
# Installation targets
#
# Create the virtual environment
venv:
	make venv/pyvenv.cfg

venv/pyvenv.cfg:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	. venv/bin/activate ; python3 -m pip install --upgrade pip
	. venv/bin/activate ; python3 -m pip install -r requirements.txt

#
# Install the lab4.services file
install-lab4-service: venv/pyvenv.cfg
	sudo install lab4.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab4
	sudo systemctl start lab4
	@# Do not overwrite lab4 as it may have been customized
	@if [ ! -r /etc/httpd/conf.d/lab4.conf ]; \
		then echo installing /etc/httpd/conf.d/lab4.conf ; \
		sudo install lab4.conf /etc/httpd/conf.d/ ; \
		else echo /etc/httpd/conf.d/lab4.conf already installed ; \
	fi
	@echo
	@echo Do not forget to edit ServerName in /etc/httpd/conf/lab4.conf, restart apache, run certbot, and restart apache again
	@echo You may also need to restart your web browser.

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
.PHONY: install-lab4-service
