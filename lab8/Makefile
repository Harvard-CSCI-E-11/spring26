#
# This is a Unix Makefile for Lab 8
# We use python to install djlint which is used to check the HTML files

export LAB=lab8
export PORT=8008

PYTHON=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

lint: $(PYTHON)
	poetry run pylint server
	poetry run pyright server

distclean:
	@echo already clean


.PHONY: distclean lint
