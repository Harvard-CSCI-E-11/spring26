#
# This is a Unix Makefile
#
# The best Makefile tutorial we have found is here:
# https://opensource.com/article/18/8/what-how-makefile
#
# For background, see:
# https://en.wikipedia.org/wiki/Make_(software)

# Create the virtual environment
venv:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	. venv/bin/activate ; python3 -m pip install -r requirements.txt

pylint:
	. venv/bin/activate; python3 -m pylint flaskr

# Run the application locally for testing
# Note: your local machine must be authorized for your AWS account with the `aws` command.
local-app:
	. venv/bin/activate; flask --app flaskr run --debug

# Print help for the application
help:
	. venv/bin/activate; flask --app flaskr --help

# Generate a new api-key
new:
	. venv/bin/activate; flask --app flaskr new-apikey
