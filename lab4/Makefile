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
.venv/pyvenv.cfg:
	poetry install

#
# Install the lab4.services file
install-lab4-service: .venv/pyvenv.cfg
	poetry install
	poetry sync
	sudo install lab4.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab4
	sudo systemctl start lab4
	@echo
	@echo Do not forget to edit /etc/nginx/sites-available/default
	@echo and restart the web server

################################################################
# Application targets
# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
local-app: .venv/pyvenv.cfg
	.venv/bin/flask --app server:app run --debug --port 8004 --reload

# Print help for the application
help: .venv/pyvenv.cfg
	.venv/bin/flask --app server:app --help

# Create a new database
init-db: .venv/pyvenv.cfg
	.venv/bin/flask --app server:app init-db

# Generate a new api-key
new-apikey: .venv/pyvenv.cfg
	.venv/bin/flask --app server:app new-apikey

# Dump the database
dump-db: .venv/pyvenv.cfg
	.venv/bin/flask --app server:app dump-db

#
# Software engineering targets

pylint: .venv/pyvenv.cfg
	.venv/bin/python3 -m pylint app



# make venv always run, even if it exists
.PHONY: install-lab4-service local-app help init-db new-apikey dump-db
