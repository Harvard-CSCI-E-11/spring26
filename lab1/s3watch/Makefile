redeploy:
	sam validate
	sam build
	AWS_PROFILE=admin-garfinkel AWS_DEFAULT_REGION=us-east-2 sam deploy

initial:
	sam build
	AWS_PROFILE=admin-garfinkel AWS_DEFAULT_REGION=us-east-2 sam deploy --guided

local-testing:
	sam local invoke LambdaFunctionName --event event.json

tail:
	AWS_PROFILE=admin-garfinkel AWS_DEFAULT_REGION=us-east-2 sam logs s3watch --tail

whoami:
	aws sts get-caller-identity


dump-bucket-policy:
	AWS_PROFILE=admin-garfinkel AWS_DEFAULT_REGION=us-east-2 aws s3api get-bucket-policy --bucket cscie-11 --query Policy --output text | jq . > bucket-policy.json
	cat bucket-policy.json
