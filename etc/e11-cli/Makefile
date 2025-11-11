# e11/Makefile
#
# The e11 module runs on both the student machine (python3.12) and on the Lambda (python3.13)

PYTHON = python3.12

.PHONY: install pytest lint clean check test

.venv/pyvenv.cfg: pyproject.toml Makefile
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update

lint: .venv/pyvenv.cfg
	poetry run pylint e11/.
	poetry run pylint e11/.

check: .venv/pyvenv.cfg
	make lint
	poetry run pytest  -q --cov=e11 --cov-report=term --cov-report=xml --junitxml=junit.xml -o junit_family=legacy tests/

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf build/ dist/
