#
# lab4
#

################################################################
# Installation targets
#
# Create the virtual environment
FLASK=.venv/bin/flask
$(FLASK):
	poetry install

#
# Install the lab4.services file
install-lab4-service: $(FLASK)
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
local-app: $(FLASK)
	$(FLASK) --app server.main:app run --debug --port 8004 --reload

# Print help for the application
help: $(FLASK)
	$(FLASK) --app server.main:app --help

# Create a new database
init-db: $(FLASK)
	$(FLASK) --app server.main:app init-db

# Wipe the database and start over
wipe-db:
	$(FLASK) --app server.main:app wipe-db
	make init-db

# Generate a new api-key
new-apikey: $(FLASK)
	$(FLASK) --app server.main:app new-apikey

# Dump the database
dump-db: $(FLASK)
	$(FLASK) --app server.main:app dump-db

#
# Software engineering targets

lint: $(FLASK)
	.venv/bin/python3 -m pylint app


# make venv always run, even if it exists
.PHONY: local-app help init-db new-apikey dump-db lint wipe-db
.PHONY: install-lab4-service
