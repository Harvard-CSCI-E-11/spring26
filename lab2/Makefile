#
# This is a Unix Makefile for Lab 2
#
# We use python to install djlint which is used to check the HTML files
# The variables LAB and PORT are set, but they aren't used.
#
# This Makefile exists to check the HTML for correctness.
# We expect that you will move the files as specified below:
#
# cp $HOME/spring26/lab2/public.html /var/www/html/
# cp $HOME/spring26/lab2/confidential.html /var/www/html/confidential/


export LAB=lab2
export PORT=8002

PYTHON=.venv/bin/python3
install: $(PYTHON)

$(PYTHON):
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

lint: $(PYTHON)
	poetry run python -m djlint .

distclean:
	@echo already clean


.PHONY: distclean lint
