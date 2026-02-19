# e11/Makefile
#
# The e11 module runs on both the student machine (python3.12) and on the Lambda (python3.13)

# DynamoDB local stuff (see end)
DYNAMODB_LOCAL_ENDPOINT=http://localhost:8000/
E11_VARS := AWS_ENDPOINT_URL_DYNAMODB=$(DYNAMODB_LOCAL_ENDPOINT)
REQ      := bin/DynamoDBLocal.jar


PYTHON = python3.12

.PHONY: pytest lint clean check test man

.venv/pyvenv.cfg: pyproject.toml Makefile
	poetry config virtualenvs.in-project true
	poetry install		# installs the current poetry.lock, do not update
	poetry install --with dev

lint: .venv/pyvenv.cfg
	poetry run pylint e11
	poetry run pyright e11

lint-all:
	make lint
	(cd lambda-home; make lint)
	(cd lambda-leaderboard; make lint)

check: .venv/pyvenv.cfg
	make lint
	poetry run pytest  -q --cov=e11 --cov-report=term --cov-report=xml --junitxml=junit.xml -o junit_family=legacy tests/

check-all:
	make check
	(cd lambda-home; make check)
	(cd lambda-leaderboard; make check)

prod-all:
	(cd lambda-home; make prod-vbd)
	(cd lambda-leaderboard; make prod-vbd)


doc/e11.1:  .venv/pyvenv.cfg
	poetry run argparse-manpage --module e11.main --function get_parser \
		--author "Simson L. Garfinkel" \
		--project-name e11 \
		--url https://github.com/Harvard-CSCI-E-11/spring26.git > doc/e11.1

man: doc/e11.1
	install -d $$HOME/.local/share/man/man1/
	install -m 0644 doc/e11.1 $$HOME/.local/share/man/man1/
	gzip -f $$HOME/.local/share/man/man1/e11.1
	mandb --quiet

clean:
	rm -f .coverage coverage.xml
	find . -name '__pycache__' -prune -exec rm -rf {} +
	rm -rf build/ dist/

distclean:
	make clean
	/bin/rm -rf .venv

install:
	pipx install --force --python "$(command -v python3.13)" .


################################################################
# DynamoDBLocal
# Installations are used by the CI pipeline and by local developers
# See https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html for info about DynamoDB (local version)

# installation:
DDBL_DOWNLOAD_URL:=https://d1ni2b6xgvw0s0.cloudfront.net/v2.x/dynamodb_local_latest.zip
bin/dynamodb_local_latest.zip:
	test -f bin/dynamodb_local_latest.zip || curl $(DDBL_DOWNLOAD_URL) -o bin/dynamodb_local_latest.zip
	test -f bin/dynamodb_local_latest.zip || (echo could not download $(DDBL_DOWNLOAD_URL); exit 1)
	find bin -ls

bin/DynamoDBLocal.jar: bin/dynamodb_local_latest.zip
	(cd bin; unzip -uq dynamodb_local_latest.zip DynamoDBLocal.jar 'DynamoDBLocal_lib/*')
	touch bin/DynamoDBLocal.jar

# operation:
start_local_dynamodb: bin/DynamoDBLocal.jar
	bash bin/local_dynamodb_control.bash start

stop_local_dynamodb:  bin/DynamoDBLocal.jar
	bash bin/local_dynamodb_control.bash stop

list-tables:
	$(PT_VARS) aws dynamodb list-tables

dump-tables:
	for tn in "users" "sessions" ; do\
		echo $$tn:; \
		$(E11_VARS) aws dynamodb describe-table --table-name $$tn ; \
		$(E11_VARS) aws dynamodb scan --max-items 5 --table-name $$tn ; \
		done


.PHONY: start_local_dynamodb stop_local_dynamodb list-tables dump-demo-tables
