# ===== e11 grader Makefile =====
TEMPLATE        ?= template.grader.yaml
STACK           ?= e11-grader
REGION          ?= us-east-1
DDB_TABLE_ARN   ?= arn:aws:dynamodb:$(REGION):000000000000:table/e11-grades
SES_FROM        ?= noreply@csci-e-11.org
SSH_SECRET_ID   ?= e11/grader/ssh_private_key
RESOLVE_S3      ?= --resolve-s3
POETRY          ?= poetry

.SILENT:
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
	echo "==> AWS identity"; aws sts get-caller-identity >/dev/null; echo "OK"

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
	@: # Build local e11 wheel with Poetry (includes e11/lab_tests)
	$(POETRY) -C ../e11 build -f wheel
	WHL=$$(ls -1 ../e11/dist/*.whl | tail -n1); \
	echo "==> Using wheel $$WHL"; \
	python -m pip install --upgrade pip >/dev/null; \
	@: # Install Lambda deps + local wheel into artifact
	python -m pip install -r $(SOURCE_DIR)/grader/requirements.txt -t $(ARTIFACTS_DIR)
	python -m pip install "$$WHL" -t $(ARTIFACTS_DIR)
	@: # Copy handler code
	rsync -a --exclude '__pycache__' $(SOURCE_DIR)/grader/ $(ARTIFACTS_DIR)/

clean-E11GraderFunction:
	rm -rf $(ARTIFACTS_DIR)/*
