# This needs to be updated to pyproject.toml and poetry

.PHONY: install lint check test clean
install:
	poetry install --with dev

check: install vend-e11
	poetry run pytest --log-cli-level=DEBUG

lint: install vend-e11
	poetry run pylint leaderboard_app

local-debug: install vend-e11
	poetry run python -c 'from leaderboard_app.flask_app import app; app.run(debug=True)'

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/using-sam-cli-sync.html
sam-sync: install
	sam sync --code --watch

.PHONY: prod-vbd stage-vbd
prod-vbd: template.yaml samconfig-prod.toml src/requirements.txt vend-e11
	echo make lint
	echo make check
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
