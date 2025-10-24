#
# lab5
#

################################################################
# Installation targets
#
# Create the virtual environment
.venv/pyvenv.cfg:
	poetry install

#
# Install the lab4.services file
install-lab5-service: .venv/pyvenv.cfg
	poetry install
	poetry sync
	sudo install lab5.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab5
	sudo systemctl start lab5
	@echo
	@echo Do not forget to edit /etc/nginx/sites-available/default
	@echo and restart the web server

################################################################
# Application targets
# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
local-app:
	.venv/bin/flask --app server.main:app run --debug --port 8005 --reload

# Print help for the application
help:
	.venv/bin/flask --app server.main:app --help

# Create a new database
instance/server_db.sqlite:
	.venv/bin/flask --app server.main:app init-db

# Create the s3 bucket and establish the CORS policy
init-s3:
	.venv/bin/flask --app server.main:app init-s3

init-db:
	.venv/bin/flask --app server.main:app init-db

# Wipe the database and start over
wipe-db:
	.venv/bin/flask --app server.main:app wipe-db
	make init-db

# Generate a new api-key
new-apikey: instance/server_db.sqlite
	.venv/bin/flask --app server.main:app new-apikey

# Dump the database
dump-db: instance/server_db.sqlite
	.venv/bin/flask --app server.main:app dump-db


#
# Software engineering targets

lint:
	.venv/bin/python3 -m pylint app


################################################################
## Healthcheck - before you start lab3

.PHONY: healthcheck
healthcheck:
	python3 -m healthcheck.main

pylint-healthcheck:
	.venv/bin/python3 -m pylint  --rcfile=healthcheck/.pylintrc healthcheck

# make .venv always run, even if it exists
.PHONY: local-app help init-db wipe-db new-apikey dump-db lint
.PHONY: install-lab5-service init-s3
