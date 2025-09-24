# ===== e11 home Makefile =====
# lambda-home is the minimal home page. It requires no e11 packages
STACK           ?= home-app
STACK_STAGE     ?= home-app-stage
CAPS            ?= CAPABILITY_IAM CAPABILITY_AUTO_EXPAND
REGION          ?= us-east-1
PROFILE         ?= fas
PYTHON          = python3.13
PIP_PLATFORM_OPTS := --platform manylinux2014_x86_64 --implementation cp --python-version 313 --only-binary=:all:
DJLINT_FLAGS ?= --profile=jinja --lint --quiet --ignore J004,J018
SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

TEMPLATE_DIR := src/home_app/templates

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONDONTWRITEBYTECODE=1

.PHONY: install vend-e11 lint pytest test
install:
	make .venv/pyvenv.cfg

.venv/pyvenv.cfg: pyproject.toml Makefile
	python3.13 -m venv .venv
	.venv/bin/pip install -e .
	.venv/bin/pip install -e ".[dev]"

vend-e11-old:
	@echo vending e11 module to src/
	rsync --archive --verbose --delete ../e11 src/home_app/ --exclude '*.pyc'

vend-e11: Makefile
	@echo "Building src/home_app/e11.whl via pip"
	( cd .. && .venv/bin/python -m pip wheel --no-deps -w dist . )
	@echo "Installing wheel into src/home_app/ as e11.whl"
	install -d src/home_app
	install -m 444 $$(ls -t ../dist/*.whl | head -1) src/home_app/e11.whl
	@echo "OK -> src/home_app/e11.whl"

lint: .venv/pyvenv.cfg
	make vend-e11
	.venv/bin/djlint $(DJLINT_FLAGS) $(TEMPLATE_DIR)/*.html
	PYTHONPATH=src/home_app/e11.whl:$(PYTHONPATH) .venv/bin/pylint src

pyright:.venv/pyvenv.cfg
	make vend-e11
	.venv/bin/pyright

pytest: .venv/pyvenv.cfg
	make vend-e11
	make lint
	make pyright
	PYTHONPATH=$$(pwd)/src/home_app/e11.whl:$(PYTHONPATH) .venv/bin/pytest -q --cov=.   --cov-report=term --cov-report=xml --log-cli-level=DEBUG tests/

test:
	make pytest


# don't specify template in deploy-prod or deploy-stage
prod-vbd: template.yaml samconfig.toml src/requirements.txt
	make vend-e11
	sam validate --config-file samconfig.toml -t template.yaml --lint
	sam build --parallel --use-container --config-file samconfig.toml -t template.yaml
	sam deploy --config-file "$$(pwd)/samconfig.toml" --no-confirm-changeset -t .aws-sam/build/template.yaml
	curl --silent  https://csci-e-11.org/ | head -3

stage-vbd: template-stage.yaml samconfig-stage.toml src/requirements.txt
	make lint
	make vend-e11
	sam validate --config-file samconfig-stage.toml -t template-stage.yaml --lint
	sam build --parallel --use-container --config-file samconfig-stage.toml -t template-stage.yaml
	sam deploy --config-file "$$(pwd)/samconfig-stage.toml" --no-confirm-changeset -t .aws-sam/build/template.yaml
	curl --silent  https://stage.csci-e-11.org/ | head -3

# sync is just not working
# Note - sync and watch don't work because the files in requirements.txt are not vendored into the src/
# directory. There are a number of workarounds but we aren't using them here.
# sync-stage: build-stage
#	make vend-e11
#	sam sync --config-file samconfig-stage.toml -t template-stage.yaml --stack-name $(STACK_STAGE) --capabilities $(CAPS)
#
# sync-watch-stage: template-stage.yaml samconfig-stage.toml src/requirements.txt
#	@echo note that SAM resolves relative paths from the template’s directory when you pass -t
#	make vend-e11
#	sam sync --config-file "$$(pwd)/samconfig-stage.toml" --stack-name home-app-stage --watch --code -t .aws-sam/build/template.yaml

src/requirements.txt: pyproject.toml Makefile .venv/pyvenv.cfg
	.venv/bin/pip-compile -q pyproject.toml --output-file src/requirements.txt

# Show function names
functions:
	@echo "Production function:"
	@aws cloudformation describe-stacks --stack-name $(STACK) --region $(REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text 2>/dev/null || echo "Stack not found"
	@echo "Stage function:"
	@aws cloudformation describe-stacks --stack-name $(STACK_STAGE) --region $(REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text 2>/dev/null || echo "Stack not found"


# Tail logs
prod-tail:
	@echo "Tailing production logs..."
	@aws logs tail "/aws/lambda/$$(aws cloudformation describe-stacks --stack-name $(STACK) --region $(REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text)" \
		--since 15m --follow --region $(REGION) --profile $(PROFILE)

# Tail stage logs (separate stack)
stage-tail:
	@echo "Tailing stage logs..."
	@aws logs tail "/aws/lambda/$$(aws cloudformation describe-stacks --stack-name $(STACK_STAGE) --region $(REGION) --profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text)" \
		--since 15m --follow --region $(REGION) --profile $(PROFILE)

# Download deployed Lambda package for inspection
fetch-zip-prod:
	@FUNC=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK) \
		--region $(REGION) \
		--profile $(PROFILE) \
		--query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' \
		--output text); \
	echo "Fetching deployment package for $$FUNC..."; \
	URL=$$(aws lambda get-function --function-name $$FUNC \
		--region $(REGION) \
		--profile $(PROFILE) \
		--query 'Code.Location' --output text); \
	/bin/rm -f lambda.zip && curl -sSL $$URL -o lambda.zip && ls -l lambda.zip && \
	echo "Deployed package extracted to lambda-package-prod/"


clean:
	/bin/rm -rf .venv
	/bin/rm -rf .aws-sam/build

# Show stage URL
urls:
	@echo "Production URL: https://csci-e-11.org/"
	@echo "Stage URL: https://stage.csci-e-11.org/"

# Show deployment info
info:
	@echo "Production Stack: $(STACK)"
	@echo "Stage Stack: $(STACK_STAGE)"
	@echo "Region: $(REGION)"
	@echo "Profile: $(PROFILE)"
	@echo ""
	@echo "Environments:"
	@echo "  Production: https://csci-e-11.org/"
	@echo "  Stage:    https://stage.csci-e-11.org/"
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
