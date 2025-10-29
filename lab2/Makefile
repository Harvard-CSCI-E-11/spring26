#
# This is a Unix Makefile for Lab 2
# We use python to install djlint which is used to check the HTML files
# THe variables LAB and PORT are set, but they aren't used.


export LAB=lab2
export PORT=8002

PYTHON:=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

lint: $(PYTHON)
	poetry run djlint *.html

distclean:
	@echo already clean


.PHONY: distclean lint
