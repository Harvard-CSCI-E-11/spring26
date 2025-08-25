# ===== e11 home Makefile =====
STACK           ?= e11-home
REGION          ?= us-east-1
PROFILE         ?= fas
RESOLVE_S3      ?= --resolve-s3
PY              = python3.12
PIP             = $(PY) -m pip
PIP_PLATFORM_OPTS := --platform manylinux2014_x86_64 --implementation cp --python-version 312 --only-binary=:all:

.SHELLFLAGS := -eu -o pipefail -c

export PIP_DISABLE_PIP_VERSION_CHECK=1
export PIP_NO_INPUT=1
export PYTHONDONTWRITEBYTECODE=1

pylint:
	poetry run pylint *.py

build: home_app/requirements.txt
	sam build -t template.yaml --cached --parallel

deploy: pylint build
	sam deploy -t template.yaml --stack-name $(STACK) --region $(REGION)

home_app/requirements.txt: ../pyproject.toml Makefile
	/bin/rm -f home_app/requirements.txt
	../.venv/bin/pip-compile ../pyproject.toml --output-file home_app/requirements.txt
	echo "-e ../" >> home_app/requirements.txt

# SAM build hooks for Lambda logical ID: E11HomeFunction
build-E11HomeFunction:
	: $${ARTIFACTS_DIR:?ARTIFACTS_DIR unset}   # guard against empty var
	rm -rf "$(ARTIFACTS_DIR)"/*
	$(PIP) install $(PIP_PLATFORM_OPTS) -r requirements.txt -t "$$ARTIFACTS_DIR"
	cp -fr home_app "$$ARTIFACTS_DIR/"
	cp -fr ../e11   "$$ARTIFACTS_DIR/"
	@[ -f "$${ARTIFACTS_DIR}/e11/__init__.py" ] || { echo "e11 missing in artifact root"; exit 3; }


clean-E11HomeFunction:
	rm -rf $(ARTIFACTS_DIR)/*
