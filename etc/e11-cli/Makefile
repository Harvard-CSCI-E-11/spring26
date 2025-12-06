# e11/Makefile
#
# The e11 module runs on both the student machine (python3.12) and on the Lambda (python3.13)

PYTHON = python3.12

.PHONY: pytest lint clean check test man

.venv/pyvenv.cfg: pyproject.toml Makefile
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update
	poetry install --with dev

lint: .venv/pyvenv.cfg
	poetry run pylint e11/.
	poetry run pyright e11/.

check: .venv/pyvenv.cfg
	make lint
	poetry run pytest  -q --cov=e11 --cov-report=term --cov-report=xml --junitxml=junit.xml -o junit_family=legacy tests/

man:  .venv/pyvenv.cfg
	poetry run argparse-manpage --module e11.main --function get_parser \
		--author "Simson L. Garfinkel" \
		--project-name e11 \
		--url https://github.com/Harvard-CSCI-E-11/spring26.git > e11.1
	install -d $$HOME/.local/share/man/man1/
	install -m 0644 e11.1 $$HOME/.local/share/man/man1/
	gzip -f $$HOME/.local/share/man/man1/e11.1
	 /usr/libexec/makewhatis $$HOME/.local/share/man
	/bin/rm -f e11.1

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf build/ dist/

distclean:
	make clean
	/bin/rm -rf .venv
