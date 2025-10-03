# e11/Makefile
#
# The e11 module runs on both the student machine (python3.12) and on the Lambda (python3.13)

PYTHON = python3.12

.PHONY: install pytest lint clean check test

install:
	make .venv/pyvenv.cfg

.venv/pyvenv.cfg: pyproject.toml Makefile
	$(PYTHON) -m venv .venv
	.venv/bin/pip install pip-tools
	.venv/bin/pip install -e .
	.venv/bin/pip install -e ".[dev]"

lint: .venv/pyvenv.cfg
	.venv/bin/pylint e11/.
	.venv/bin/pyright e11/.

check: .venv/pyvenv.cfg
	make lint
	.venv/bin/pytest -q --cov=e11 --cov-report=term --cov-report=xml --junitxml=junit.xml -o junit_family=legacy tests/

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf build/ dist/
