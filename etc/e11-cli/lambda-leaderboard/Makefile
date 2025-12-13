# This needs to be updated to pyproject.toml and poetry

.PHONY: install lint check test clean
install:
	poetry install --with dev

check: vend-e11 lint create-local-table
	@echo "--- Running tests with pytest ---"
	$(AWS_VARS) poetry run pytest -q --cov=. --cov-report=term --cov-report=xml --junitxml=junit.xml -o junit_family=legacy --log-cli-level=DEBUG

lint: install vend-e11
	poetry run pylint leaderboard_app

local-debug: install vend-e11
	poetry run python -c 'from leaderboard_app.flask_app import app; app.run(debug=True)'

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-sync.html
sam-sync: install
	sam sync --code --watch

.PHONY: prod-vbd stage-vbd
prod-vbd: template.yaml samconfig-prod.toml src/requirements.txt vend-e11
	make lint
	make check
	sam validate --config-file samconfig-prod.toml -t template.yaml --lint
	sam build --parallel --use-container --config-file samconfig-prod.toml -t template.yaml
	sam deploy --config-file "$$(pwd)/samconfig-prod.toml"  --parameter-overrides DeploymentTimestamp="$$(date +'%Y-%m-%dT%H:%M:%S%z %Z')" --no-confirm-changeset -t .aws-sam/build/template.yaml
	curl --silent  https://leaderboard.csci-e-11.org/ | head -3

prod-tail:
	sam logs --stack-name leaderboard --name LeaderboardFlaskFunction --tail   --region us-east-1   --profile fas

# This target generates the requirements.txt for SAM to use
src/requirements.txt: poetry.lock pyproject.toml
	@echo "--- Exporting requirements.txt from Poetry ---"
	poetry export -f requirements.txt --output src/requirements.txt --without-hashes

# Useful functions
list-cloud-resources:
	aws cloudformation list-stack-resources \
	  --stack-name leaderboard --region us-east-1 --profile fas \
	  --query "StackResourceSummaries[?ResourceType=='AWS::ApiGatewayV2::DomainName'].[LogicalResourceId,PhysicalResourceId,ResourceStatus]" \
	  --output table


# --- Custom Vendoring
.PHONY: vend-e11
vend-e11: install
	@echo "Building src/leaderboard_app/e11.whl via pip"
	( cd .. && poetry run python -m pip wheel --no-deps -w dist . )
	@echo "Installing wheel into src/leaderboard_app/ as e11.whl"
	install -d src/leaderboard_app
	install -m 444 $$(ls -t ../dist/*.whl | head -1) src/leaderboard_app/e11.whl
	@echo "OK -> src/leaderboard_app/e11.whl"

distclean:
	/bin/rm -rf .venv
	/bin/rm -f instance/message_board.db

################################################################
# DynamoDBLocal
# Installations are used by the CI pipeline and by local developers
# See https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html for info about DynamoDB (local version)

# Local DynamoDB endpoint
DYNAMODB_LOCAL_ENDPOINT=http://localhost:8010/
AWS_ENDPOINT_URL_DYNAMODB := $(DYNAMODB_LOCAL_ENDPOINT)
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_DEFAULT_REGION=us-east-1

# AWS_VARS are required for any command that uses AWS
AWS_VARS := AWS_ACCESS_KEY_ID=minioadmin AWS_SECRET_ACCESS_KEY=minioadmin AWS_DEFAULT_REGION=us-east-1 AWS_ENDPOINT_URL_DYNAMODB=$(DYNAMODB_LOCAL_ENDPOINT)

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
	$(AWS_VARS) aws dynamodb list-tables --endpoint-url $(DYNAMODB_LOCAL_ENDPOINT)

# Create the Leaderboard table for local testing
create-local-table: start_local_dynamodb
	@echo "Creating Leaderboard table in local DynamoDB..."
	$(AWS_VARS) aws dynamodb create-table \
		--endpoint-url $(DYNAMODB_LOCAL_ENDPOINT) \
		--table-name Leaderboard \
		--attribute-definitions AttributeName=name,AttributeType=S \
		--key-schema AttributeName=name,KeyType=HASH \
		--billing-mode PAY_PER_REQUEST \
		--region us-east-1 || echo "Table may already exist"

.PHONY: start_local_dynamodb stop_local_dynamodb list-tables create-local-table
