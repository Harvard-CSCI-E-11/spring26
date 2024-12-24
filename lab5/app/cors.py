# Define the CORS configuration
CORS_CONFIGURATION = {
    'CORSRules': [
        {
            'AllowedOrigins': ['*'],               # Allow all origins with presigned POST and GETs
            'AllowedMethods': ['GET', 'POST', 'PUT'],     # Methods to allow
            'AllowedHeaders': ['*'],               # Allow all headers
            'MaxAgeSeconds': 3000                  # Cache duration for preflight requests
        }
    ]
}

def apply_cors(app):
    # Apply the CORS policy to the S3 bucket
    s3 = boto3.client('s3')
    s3.put_bucket_cors(
        Bucket=app.config['S3_BUCKET'],
        CORSConfiguration=CORS_CONFIGURATION
    )

