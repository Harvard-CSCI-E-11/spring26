# ===== e11 home Makefile =====
TEMPLATE        ?= template.yaml
STACK           ?= e11-home
REGION          ?= us-east-1
PROFILE         ?= fas
DDB_TABLE_ARN   ?= arn:aws:dynamodb:$(REGION):000000000000:table/e11-grades
RESOLVE_S3      ?= --resolve-s3
POETRY          ?= poetry
PKG_ROOT        ?= ..
# Resolve paths from where THIS Makefile lives (robust under sam's temp SOURCE_DIR)
MAKEFILE_DIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
PROJECT_ROOT := $(abspath $(MAKEFILE_DIR)/..)
PY              = python3.12
PIP             = $(PY) -m pip
PIP_PLATFORM_OPTS := --platform manylinux2014_x86_64 --implementation cp --python-version 312 --only-binary=:all:



.SHELLFLAGS := -eu -o pipefail -c

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONDONTWRITEBYTECODE=1

.PHONY: help print check build deploy \
        build-E11HomeFunction clean-E11HomeFunction

guard-%:
	@if [ -z "$($*)" ]; then echo "Missing required variable: $*"; exit 1; fi

check: guard-DDB_TABLE_ARN
	echo "==> SAM validate"; sam validate -t $(TEMPLATE)
	echo "==> AWS identity"; aws --profile=$(PROFILE) sts get-caller-identity >/dev/null; echo "OK"

pylint:
	poetry run pylint *.py

build:
	echo "==> sam build -t $(TEMPLATE)"; sam build -t $(TEMPLATE) --cached --parallel

deploy: check build
	echo "==> sam deploy"
	sam deploy -t $(TEMPLATE) \
	  --stack-name $(STACK) --region $(REGION) \
	  --capabilities CAPABILITY_IAM $(RESOLVE_S3) \
	  --parameter-overrides \
	    DynamoTableArn="$(DDB_TABLE_ARN)"
	echo "Deployed stack: $(STACK) in $(REGION)"

requirements.txt: ../pyproject.toml
	poetry -C .. export --only main --without-hashes -o "$(MAKEFILE_DIR)/requirements.txt"

# SAM build hooks for Lambda logical ID: E11HomeFunction
build-E11HomeFunction:
	: $${ARTIFACTS_DIR:?ARTIFACTS_DIR unset}   # guard against empty var
	rm -rf "$(ARTIFACTS_DIR)"/*
	$(PIP) install $(PIP_PLATFORM_OPTS) -r "$(MAKEFILE_DIR)/requirements.txt" -t "$$ARTIFACTS_DIR"
	$(PIP) install $(PIP_PLATFORM_OPTS) "$(PROJECT_ROOT)" -t "$$ARTIFACTS_DIR"
	cp -f home.py "$$ARTIFACTS_DIR/"
	cp -fr static "$$ARTIFACTS_DIR/"
	@[ -f "$${ARTIFACTS_DIR}/e11/__init__.py" ] || { echo "e11 missing in artifact root"; exit 3; }


clean-E11HomeFunction:
	rm -rf $(ARTIFACTS_DIR)/*
