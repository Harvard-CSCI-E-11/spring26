################################################################
# Installation targets
#
# Create the virtual environment for running circuitpython tools

export LAB=lab7

PYTHON=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update
	poetry install --with dev

memento-install: $(PYTHON) requirements_cp.txt
	poetry run circup install -r requirements_cp.txt

lint: $(PYTHON)
	poetry run pylint *.py
	poetry run pyright *.py

distclean:
	/bin/rm -rf .venv

.PHONY: distclean lint memento-install
