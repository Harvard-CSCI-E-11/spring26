# e11/Makefile
.PHONY: install pytest clean

install:
	python3.13 -m venv .venv
	.venv/bin/pip install pip-tools
	.venv/bin/pip install -e .
	.venv/bin/pip install ".[dev]"

pytest: install
	.venv/bin/pytest -q --maxfail=1 --disable-warnings --cov=e11 --cov-report=term-missing --cov-report=xml

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
