#
# This is a Unix Makefile for Lab 8
# We use python to install djlint which is used to check the HTML files

PYTHON=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

pub1:
	cp camera1.py /Volumes/CIRCUITPY/code.py

pub2:
	cp camera2.py /Volumes/CIRCUITPY/code.py

pub3:
	cp camera3.py /Volumes/CIRCUITPY/code.py


memento-install: $(PYTHON) requirements_cp.txt
	poetry run circup install -r requirements_cp.txt

lint: $(PYTHON)
	poetry run pylint *.py

# Don't have pyright working yet here.
#poetry run pyright *.py

distclean:
	/bin/rm -rf .venv

.PHONY: distclean lint memento-install
