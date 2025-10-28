#
# This is a Unix Makefile for lab4
#
# It is different from lab3, in that:
# - we now provide targets for automatically installing the lab4 service the lab4 nginx site
# -

################################################################
# Installation targets
#
# Create the virtual environment
FLASK=.venv/bin/flask

$(FLASK):
	poetry config virtualenvs.in-project true
	poetry install		# includes flask in pyproject.toml

#
# Install the lab4.services file
install-lab4-service: $(FLASK)
	poetry install
	sudo install lab4.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab4
	sudo systemctl start lab4

install-lab4-nginx:
	@echo TODO - install the new site and run lets encrypt

################################################################
# Application targets
# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
local-app: $(FLASK)
	poetry run flask  --app server.main:app run --debug --port 8004 --reload

# Print help for the application
help: $(FLASK)
	poetry run flask  --app server.main:app --help

# Create a new database
init-db: $(FLASK)
	poetry run flask  --app server.main:app init-db

# Wipe the database and start over
wipe-db:
	poetry run flask  --app server.main:app wipe-db
	make init-db

# Generate a new api-key
new-apikey: $(FLASK)
	poetry run flask  --app server.main:app new-apikey

# Dump the database
dump-db: $(FLASK)
	poetry run flask  --app server.main:app dump-db

#
# Software engineering targets

lint: $(FLASK)
	poetry run pylint server

# make venv always run, even if it exists
.PHONY: local-app help init-db new-apikey dump-db lint wipe-db
.PHONY: install-lab4-service
