# ===== e11 grader Makefile =====
TEMPLATE        ?= template.yaml
STACK           ?= e11-grader
REGION          ?= us-east-1
PROFILE         ?= fas
DDB_TABLE_ARN   ?= arn:aws:dynamodb:$(REGION):000000000000:table/e11-grades
SES_FROM        ?= noreply@csci-e-11.org
SSH_SECRET_ID   ?= e11/grader/ssh_private_key
RESOLVE_S3      ?= --resolve-s3
POETRY          ?= poetry
SOURCE_DIR     ?= $(CURDIR)
ARTIFACTS_DIR  ?= $(CURDIR)/.aws-sam/build/E11GraderFunction
PKG_ROOT        ?= ..
PY              = python3.12
PIP             = $(PY) -m pip
# Resolve paths from where THIS Makefile lives (robust under sam's temp SOURCE_DIR)
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(MAKEFILE_DIR)/..)



.PHONY: help print check build deploy \
        build-E11GraderFunction clean-E11GraderFunction

help:
	echo "Targets: check, build, deploy"

print:
	echo TEMPLATE=$(TEMPLATE); echo STACK=$(STACK); echo REGION=$(REGION)
	echo DDB_TABLE_ARN=$(DDB_TABLE_ARN); echo SES_FROM=$(SES_FROM); echo SSH_SECRET_ID=$(SSH_SECRET_ID)

guard-%:
	@if [ -z "$($*)" ]; then echo "Missing required variable: $*"; exit 1; fi

check: guard-DDB_TABLE_ARN guard-SES_FROM guard-SSH_SECRET_ID
	echo "==> SAM validate"; sam validate -t $(TEMPLATE)
	echo "==> AWS identity"; aws --profile=$(PROFILE) sts get-caller-identity >/dev/null; echo "OK"

build:
	echo "==> sam build -t $(TEMPLATE)"; sam build -t $(TEMPLATE) --cached --parallel

deploy: check build
	echo "==> sam deploy"
	sam deploy -t $(TEMPLATE) \
	  --stack-name $(STACK) --region $(REGION) \
	  --capabilities CAPABILITY_IAM $(RESOLVE_S3) \
	  --parameter-overrides \
	    DynamoTableArn="$(DDB_TABLE_ARN)" \
	    SesFromAddress="$(SES_FROM)" \
	    SshSecretId="$(SSH_SECRET_ID)"
	echo "Deployed stack: $(STACK) in $(REGION)"

# SAM build hooks for Lambda logical ID: E11GraderFunction
build-E11GraderFunction:
	@echo "PY=$(PY)"
	@echo "SOURCE_DIR=$(SOURCE_DIR)"
	@echo "PROJECT_ROOT=$(PROJECT_ROOT)"
	@echo "ARTIFACTS_DIR=$(ARTIFACTS_DIR)"
	mkdir -p $(ARTIFACTS_DIR)
	poetry export  --without-hashes -o requirements.txt
	@[ -f "$(PROJECT_ROOT)/pyproject.toml"  ] || { echo "$(PROJECT_ROOT)/pyproject.toml is missing"; exit 2; }
	@[ -f "$(PROJECT_ROOT)/e11/__init__.py" ] || { echo "$(PROJECT_ROOT)/e11/__init__.py is missing"; exit 2; }
	$(PIP) install -r $(SOURCE_DIR)/requirements.txt -t $(ARTIFACTS_DIR)
	$(PIP) install $(PROJECT_ROOT) -t $(ARTIFACTS_DIR)
	cp -f $(SOURCE_DIR)/grader.py $(ARTIFACTS_DIR)/

clean-E11GraderFunction:
	rm -rf $(ARTIFACTS_DIR)/*
