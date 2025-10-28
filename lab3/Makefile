#
# This is a Unix Makefile for lab3
#
# The best Makefile tutorial we have found is here:
# https://opensource.com/article/18/8/what-how-makefile
#
# For background, see:
# https://en.wikipedia.org/wiki/Make_(software)

PYTHON:=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

distclean:
	/bin/rm -rf .venv
	/bin/rm -f students.db

.PHONY: lint
lint: $(PYTHON)
	poetry run student_data.py
	poetry run simple_flask_application.py
