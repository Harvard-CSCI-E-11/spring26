# Deprecated s3 watcher

Previously we just watched S3 for uploaded files.

Nov 26, 2026
First try:
https://chatgpt.com/share/674607e9-3670-8010-956f-e4ee7e16fe17

SAM can't read events from an existing bucket:
https://github.com/aws/serverless-application-model/issues/124
https://aws.amazon.com/blogs/compute/using-dynamic-amazon-s3-event-handling-with-amazon-eventbridge/

The workaround is to use an s3-to-lambda pattern from here:
https://github.com/aws-samples/s3-to-lambda-patterns/tree/master/eventbridge

and specifically:
https://github.com/aws-samples/s3-to-lambda-patterns/tree/master/eventbridge/2-existing-bucket

sam init

Deploy the SAM stack:
sam build
sam deploy --guided
