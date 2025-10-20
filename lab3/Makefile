# lab3

install: .venv/bin/python3

.venv/bin/python3:
	poetry config virtualenvs.in-project true
	poetry install

distclean:
	/bin/rm -rf .venv
	/bin/rm -f students.db

.PHONY: lint
lint: .venv/bin/python3
	.venv/bin/python3 -m pylint student_data.py
	.venv/bin/python3 -m pylint simple_flask_application.py
