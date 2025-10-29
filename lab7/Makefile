################################################################
# Installation targets
#
# Create the virtual environment

PYTHON:=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

venv/pyvenv.cfg:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	venv/bin/python3 -m pip install --upgrade pip
	venv/bin/python3 -m pip install -r requirements.txt
