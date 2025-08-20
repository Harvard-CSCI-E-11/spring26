# e11/Makefile
.PHONY: install pytest clean
POETRY ?= poetry

install:
	@set -e; \
	if [ ! -x .venv/bin/python ]; then \
	  python3.12 -m venv .venv; \
	fi; \
	$(POETRY) config virtualenvs.create true --local; \
	$(POETRY) config virtualenvs.in-project true --local; \
	$(POETRY) env use .venv/bin/python; \
	$(POETRY) sync

pytest: install
	$(POETRY) run pytest -q --maxfail=1 --disable-warnings \
	  --cov=e11 --cov-report=term-missing --cov-report=xml

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
