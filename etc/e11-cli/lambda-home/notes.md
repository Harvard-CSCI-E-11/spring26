installHook.js:1 Delete failed: 500  body: {"error": true, "message": "An error occurred (AccessDenied) when calling the DeleteObject operation: User: arn:aws:sts::586794483136:assumed-role/home-app-prod-E11HomeFunctionRole-Pw7fA6momSlH/home-app-prod-E11HomeFunction-9BWcNJ0jnNq4 is not authorized to perform: s3:DeleteObject on resource: \"arn:aws:s3:::csci-e-11/images/58ad7091-da9e-4f80-a4c5-8edab8a8f4f8.jpeg\" because no identity-based policy allows the s3:DeleteObject action", "session_id": "d546cb77-1826-49bd-b387-9746221f1162"}


Because the template said:
            - Sid: AccessExistingBucket
              Effect: Allow
              Action:
                - s3:GetObject
                - s3:PutObject
              Resource:
                - !Sub 'arn:aws:s3:::${ImageBucketName}'      # The Bucket itself
                - !Sub 'arn:aws:s3:::${ImageBucketName}/*'    # The Objects inside

and not:


