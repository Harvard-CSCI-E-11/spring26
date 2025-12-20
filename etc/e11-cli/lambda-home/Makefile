# ===== e11 home Makefile (Poetry Version) =====
# Uses Poetry for dependency management and Make for SAM/AWS task running.
#
# Note: everything must be in same AWS region

# SAM/AWS Configuration (unchanged)
STACK_PROD      ?= home-app-prod
STACK_STAGE     ?= home-app-stage
CAPS            ?= CAPABILITY_IAM CAPABILITY_AUTO_EXPAND
AWS_REGION      ?= us-east-1
PROFILE         ?= fas
DJLINT_FLAGS    ?= --profile=jinja --lint --quiet --ignore J004,J018
TEMPLATE_DIR    := src/home_app/templates
S3_BUCKET       ?= csci-e-11
AWS_PROFILE     ?= fas
ROOT_DOMAIN     ?= csci-e-11.org

# Shell Configuration (unchanged)
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

# Environment setup (unchanged)
export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONDONTWRITEBYTECODE=1

# --- Poetry-based Targets ---

.PHONY: install lint check test clean
install:
	@echo "--- Installing dependencies with Poetry ---"
	poetry install --with dev

# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html
install-sam-ubuntu:
	curl -L https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip -o aws-sam-cli-linux-x86_64.zip
	unzip aws-sam-cli-linux-x86_64.zip -d sam-installation
	sudo ./sam-installation/install
	sam --version
	/bin/rm -rf aws-sam-cli-linux-x86_64.zip sam-installation

lint: vend-e11
	@echo "--- Validating imports from vendored wheel ---"
	poetry run pytest -xvs tests/test_import_validation.py
	poetry run djlint $(DJLINT_FLAGS) $(TEMPLATE_DIR)/*.html
	poetry run ruff check --fix
	poetry run pylint src
	poetry run pyright src
	sam validate --config-file samconfig-prod.toml -t template.yaml --lint
	sam validate --config-file samconfig-stage.toml -t template.yaml --lint

check: vend-e11 lint
	@echo "--- Running tests with pytest ---"
	poetry run pytest -q --cov=. --cov-report=term --cov-report=xml --junitxml=junit.xml -o junit_family=legacy --log-cli-level=DEBUG tests/

# This target generates the requirements.txt for SAM to use
src/requirements.txt: poetry.lock pyproject.toml
	@echo "--- Exporting requirements.txt from Poetry ---"
	poetry export -f requirements.txt --output src/requirements.txt --without-hashes

distclean:
	@echo "--- Cleaning up project files ---"
	/bin/rm -rf .venv
	/bin/rm -rf .aws-sam/build
	/bin/rm -f src/requirements.txt
	/bin/rm -f poetry.lock
	/bin/rm -f lambda.zip
	/bin/rm -rf .mypy_cache .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} +

# --- Custom Vendoring
.PHONY: vend-e11
vend-e11: install
	@echo "Building src/home_app/e11.whl via pip"
	( cd .. && poetry run python -m pip wheel --no-deps -w dist . )
	@echo "Installing wheel into src/home_app/ as e11.whl"
	install -d src/home_app
	install -m 444 $$(ls -t ../dist/*.whl | head -1) src/home_app/e11.whl
	@echo "OK -> src/home_app/e11.whl"

# --- AWS SAM/CLI Targets
# These are deployment tasks, perfect for Make.
# They now depend on the new poetry-based targets.

.PHONY: prod-vbd stage-vbd
prod-vbd: template.yaml samconfig-prod.toml src/requirements.txt vend-e11 lint
	sam validate --config-file samconfig-prod.toml -t template.yaml --lint
	sam build --parallel --use-container --config-file samconfig-prod.toml -t template.yaml
	sam deploy --config-file "$$(pwd)/samconfig-prod.toml"  \
		--parameter-overrides DeploymentTimestamp="$$(date +'%Y-%m-%dT%H:%M:%S%z %Z')" \
		--no-confirm-changeset -t .aws-sam/build/template.yaml
	curl --silent  https://$(ROOT_DOMAIN)/ | head -3

stage-vbd: template.yaml samconfig-stage.toml src/requirements.txt vend-e11
	sam validate --config-file samconfig-stage.toml -t template.yaml --lint
	sam build --parallel --use-container --config-file samconfig-stage.toml -t template.yaml
	sam deploy --config-file "$$(pwd)/samconfig-stage.toml" --parameter-overrides DeploymentTimestamp="$$(date +'%Y-%m-%dT%H:%M:%S%z %Z')" --no-confirm-changeset -t .aws-sam/build/template.yaml
	curl --silent  https://stage.$(ROOT_DOMAIN)/ | head -3

# Show function names
.PHONY: functions
functions:
	@echo "Production function:"
	aws cloudformation describe-stacks --stack-name $(STACK_PROD) --region $(AWS_REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text 2>/dev/null || echo "Stack not found"
	@echo "Stage function:"
	aws cloudformation describe-stacks --stack-name $(STACK_STAGE) --region $(AWS_REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text 2>/dev/null || echo "Stack not found"

# Tail logs
.PHONY: prod-tail
prod-tail:
	@echo "Tailing production logs..."
	@aws logs tail "/aws/lambda/$$(aws cloudformation describe-stacks --stack-name $(STACK_PROD) --region $(AWS_REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text)" \
		--since 15m --follow --region $(AWS_REGION) --profile $(PROFILE)

# Tail stage logs (separate stack)
.PHONY: stage-tail
stage-tail:
	@echo "Tailing stage logs..."
	@aws logs tail "/aws/lambda/$$(aws cloudformation describe-stacks --stack-name $(STACK_STAGE) --region $(AWS_REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text)" \
		--since 15m --follow --region $(AWS_REGION) --profile $(PROFILE)

# Download deployed Lambda package for inspection
.PHONY: fetch-zip-prod
fetch-zip-prod:
	@FUNC=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_PROD) \
		--region $(AWS_REGION) \
		--profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' \
		--output text); \
	echo "Fetching deployment package for $$FUNC..."; \
	URL=$$(aws lambda get-function --function-name $$FUNC \
		--region $(AWS_REGION) \
		--profile $(PROFILE) \
		--query 'Code.Location' --output text); \
	/bin/rm -f lambda.zip && curl -sSL $$URL -o lambda.zip && ls -l lambda.zip && \
	echo "Deployed package extracted to lambda-package-prod/"

# Show stage URL
.PHONY: urls
urls:
	@echo "Production URL: https://$(ROOT_DOMAIN).org/"
	@echo "Stage URL: https://stage.$(ROOT_DOMAIN).org/"

# Show deployment info
.PHONY: info
info:
	@echo "Production Stack: $(STACK_PROD)"
	@echo "Stage Stack: $(STACK_STAGE)"
	@echo "Region: $(AWS_REGION)"
	@echo "Profile: $(PROFILE)"
	@echo ""
	@echo "Environments:"
	@echo "  Production: https://$(ROOT_DOMAIN).org/"
	@echo "  Stage:    https://stage.$(ROOT_DOMAIN).org/"
	@echo ""
	@echo "Deployment Options:"
	@echo "  make deploy          - Deploy stage only (default)"
	@echo "  make deploy-prod     - Deploy production only"
	@echo "  make deploy-stage    - Deploy stage only (same as deploy)"
	@echo ""
	@echo "Template Management:"
	@echo "  make template.yaml     - Generate production template"
	@echo "  make template-stage.yaml - Generate stage template"
	@echo ""
	@echo "Debugging:"
	@echo "  make functions      - Show function names from stacks"
	@echo "  make tail           - Tail production logs"
	@echo "  make tail-stage     - Tail stage logs"


#
# Validate S3 rules
#
s3-install-rules:
	aws s3api --profile $(AWS_PROFILE) put-bucket-notification-configuration \
	    --bucket $(S3_BUCKET) \
	    --notification-configuration '{ "EventBridgeConfiguration": {} }'

s3-validate-rules-and-region:
	aws s3api --profile $(AWS_PROFILE) get-bucket-notification-configuration --bucket $(S3_BUCKET) | \
		grep EventBridgeConfiguration && echo "✅ EventBridge is ENABLED"
	aws --profile=$(AWS_PROFILE) s3api get-bucket-location --bucket $(S3_BUCKET) | sed s/null/$(AWS_REGION)/ | grep $(AWS_REGION) && echo "✅ S3 bucket in correct region"
