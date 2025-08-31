# ===== e11 home Makefile =====
# lambda-home is the minimal home page. It requires no e11 packages
STACK           ?= home-app
STACK_STAGE     ?= home-app-stage
REGION          ?= us-east-1
PROFILE         ?= fas
PY              = python3.13
PIP_PLATFORM_OPTS := --platform manylinux2014_x86_64 --implementation cp --python-version 313 --only-binary=:all:

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONDONTWRITEBYTECODE=1

.PHONY: install
install:
	make .venv/pyvenv.cfg

.venv/pyvenv.cfg: pyproject.toml Makefile
	$(PY) -m venv .venv
	.venv/bin/pip install -e .
	.venv/bin/pip install -e ".[dev]"

pytest: .venv/pyvenv.cfg
	.venv/bin/python -m pytest -v --cov=. --cov-report=xml --cov-report=html --log-cli-level=DEBUG tests

pylint: .venv/pyvenv.cfg
	.venv/bin/pylint src

# Generate YAML templates from parts
template.yaml: template-top.yaml template-common.yaml template-bottom.yaml
	cat template-top.yaml template-common.yaml template-bottom.yaml > template.yaml

# Generate stage template only
template-stage.yaml: template-stage-top.yaml template-common.yaml template-stage-bottom.yaml
	cat template-stage-top.yaml template-common.yaml template-stage-bottom.yaml > template-stage.yaml

# Build the Lambda function (default: staging)
build: template.yaml samconfig.toml src/requirements.txt
	sam build --parallel --config-file samconfig.toml -t template.yaml

# Deploy to stage environment (default)
deploy: template.yaml samconfig.toml src/requirements.txt
	sam deploy --config-file samconfig-stage.toml

# Stage deployment (explicit)
build-stage: template-stage.yaml samconfig-stage.toml src/requirements.txt
	sam build --parallel --config-file samconfig-stage.toml -t template-stage.yaml

deploy-stage: template-stage.yaml samconfig-stage.toml src/requirements.txt
	sam deploy --config-file samconfig-stage.toml

# Tail production logs
tail:
	@echo "Tailing production logs..."
	@aws logs tail "/aws/lambda/$$(aws cloudformation describe-stacks --stack-name $(STACK) --region $(REGION) --profile $(PROFILE) --query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text)" --since 15m --follow --region $(REGION) --profile $(PROFILE)

# Tail stage logs (separate stack)
tail-stage:
	@echo "Tailing stage logs..."
	@aws logs tail "/aws/lambda/$$(aws cloudformation describe-stacks --stack-name $(STACK_STAGE) --region $(REGION) --profile $(PROFILE) --query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text)" --since 15m --follow --region $(REGION) --profile $(PROFILE)

# Show function names
functions:
	@echo "Production function:"
	@aws cloudformation describe-stacks --stack-name $(STACK) --region $(REGION) --profile $(PROFILE) --query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text 2>/dev/null || echo "Stack not found"
	@echo "Stage function:"
	@aws cloudformation describe-stacks --stack-name $(STACK_STAGE) --region $(REGION) --profile $(PROFILE) --query 'Stacks[0].Outputs[?OutputKey==`HomeFunction`].OutputValue' --output text 2>/dev/null || echo "Stack not found"

src/requirements.txt: pyproject.toml Makefile
	.venv/bin/pip-compile -q pyproject.toml --output-file src/requirements.txt

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
