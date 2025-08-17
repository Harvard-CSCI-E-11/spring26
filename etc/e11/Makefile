# Run tests with Poetry; produce coverage.xml for Codecov
.PHONY: pytest install-dev clean

POETRY ?= poetry

install-dev:
	$(POETRY) install --sync
	@: # Ensure pytest deps exist inside Poetry venv (only if not declared in pyproject)

pytest: install-dev
	@: # Use Poetry venv for execution and coverage
	PYTHONWARNINGS=default $(POETRY) run pytest -q \
	  --maxfail=1 --disable-warnings \
	  --cov=e11 --cov-report=term-missing --cov-report=xml

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
