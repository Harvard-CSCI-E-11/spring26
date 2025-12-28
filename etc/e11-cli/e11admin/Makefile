.PHONY: lint clean

.venv/pyvenv.cfg: pyproject.toml Makefile
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update
	poetry install --with dev

lint: .venv/pyvenv.cfg
	poetry run pylint e11/.
	poetry run pyright e11/.
