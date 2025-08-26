# ===== e11 home Makefile =====
# lambda-home is the minimal home page. It requires no e11 packages
STACK           ?= home-app
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
	.venv/bin/pytest

pylint: .venv/pyvenv.cfg
	.venv/bin/pylint *.py

build: src/requirements.txt
	sam build --parallel

deploy: src/requirements.txt
	sam deploy --stack-name $(STACK) --region $(REGION)

src/requirements.txt: pyproject.toml Makefile
	.venv/bin/pip-compile -q pyproject.toml --output-file src/requirements.txt


clean:
	/bin/rm -rf .venv
	/bin/rm -rf .aws-sam/build

#
# SAM build hooks for Lambda logical ID: E11HomeFunction
# build-E11HomeFunction:
# 	: $${ARTIFACTS_DIR:?ARTIFACTS_DIR unset}   # guard against empty var
# 	rm -rf "$(ARTIFACTS_DIR)"/*
# 	$(PIP) install $(PIP_PLATFORM_OPTS) -r requirements.txt -t "$$ARTIFACTS_DIR"
# 	cp -fr home_app "$$ARTIFACTS_DIR/"
# 	cp -fr ../e11   "$$ARTIFACTS_DIR/"
# 	@[ -f "$${ARTIFACTS_DIR}/e11/__init__.py" ] || { echo "e11 missing in artifact root"; exit 3; }
#
#
# clean-E11HomeFunction:
# 	rm -rf $(ARTIFACTS_DIR)/*
#
