AWS_PROFILE:=fas
AWS_REGION=us-east-2

redeploy:
	sam validate
	sam build
	AWS_PROFILE=$(AWS_PROFILE) AWS_DEFAULT_REGION=$(AWS_REGION) sam deploy

initial:
	sam build
	AWS_PROFILE=$(AWS_PROFILE) AWS_DEFAULT_REGION=$(AWS_REGION) sam deploy --guided

local-testing:
	sam local invoke LambdaFunctionName --event event.json

tail:
	AWS_PROFILE=$(AWS_PROFILE) AWS_DEFAULT_REGION=$(AWS_REGION) sam logs s3watch --tail

whoami:
	aws sts get-caller-identity


dump-bucket-policy:
	AWS_PROFILE=$(AWS_PROFILE) AWS_DEFAULT_REGION=$(AWS_REGION) \
		aws s3api get-bucket-policy --bucket cscie-11 --query Policy --output text | jq . > bucket-policy.json
	cat bucket-policy.json

stats:
	aws --profile=$(AWS_PROFILE) --region=$(AWS_REGION) lambda list-functions --query 'Functions[*].FunctionName' --output table |cat
	aws --profile=$(AWS_PROFILE) --region=$(AWS_REGION) cloudwatch get-metric-statistics \
	    --namespace AWS/Lambda \
	    --metric-name Invocations \
	    --start-time $$(date -v -1m +%Y-%m-%dT%H:%M:%S) \
	    --end-time $$(date +%Y-%m-%dT%H:%M:%S) \
	    --period 86400 \
	    --statistics Sum \
	    --dimensions Name=FunctionName,Value=s3watch-EventConsumerFunction-9yam7GLZdf0T \
	    --output table |cat

################################################################
# Software engineering
# This is still pip-based, alas.
venv:
	echo create the virtual environment and install the requirements
	python3 -m venv venv
	. venv/bin/activate ; python3 -m pip install -r requirements.txt

pylint:
	. venv/bin/activate ; python3 -m pylint event_consumer

clean:
	find . -name '*~' -exec rm {} \;



.PHONY: venv
.PHONY: pylint
