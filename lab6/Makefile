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
