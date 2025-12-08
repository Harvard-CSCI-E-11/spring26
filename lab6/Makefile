# This is a Unix Makefile for lab6
#
# It is different from lab5, in that:
# -
# -

################################################################
# Installation targets
#
# Create the virtual environment
export LAB=lab6
export PORT=8006

PYTHON=.venv/bin/python6
$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install

#
# Install the lab4.services file
install-lab6-service:
	sudo install lab6.service /etc/systemd/system/
	sudo systemctl daemon-reload
	sudo systemctl enable lab6
	sudo systemctl start lab6

install-lab6-nginx:
	@echo TODO - install the new site and run lets encrypt


################################################################
# Application targets
# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
local-app: $(PYTHON)
	poetry run flask --app server.main:app run --debug --port 8006 --reload

# Print help for the application
help: $(PYTHON)
	poetry run flask --app server.main:app --help

# Create a new database
init-db: $(PYTHON)
	@poetry run flask --app server.main:app init-db

# Wipe the database and start over
wipe-db: $(PYTHON)
	poetry run flask --app server.main:app wipe-db
	make init-db

# Generate a new api-key
new-apikey: $(PYTHON)
	@poetry run flask --app server.main:app new-apikey

# Dump the database
dump-db: $(PYTHON)
	poetry run flask  --app server.main:app dump-db

#
# Software engineering targets

lint: $(PYTHON)
	poetry run pylint server
	poetry run pyright *.py

distclean:
	/bin/rm -rf .venv
	/bin/rm -f instance/message_board.db

# make .venv always run, even if it exists
.PHONY: local-app help init-db wipe-db new-apikey dump-db lint distclean
.PHONY: install-lab6-service init-s3

#### lab5 additions follow

# Create the s3 bucket and establish the CORS policy
init-s3:
	poetry run flask --app server.main:app init-s3
