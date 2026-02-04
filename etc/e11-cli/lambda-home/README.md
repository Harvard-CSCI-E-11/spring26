# Lambda-Home

Lambda-Home is the AWS Lambda function that powers the CSCI E-11 student dashboard at `https://csci-e-11.org/`. It handles student registration, processes grading requests, and provides the web interface where students can view their grades and course status. The function authenticates users via Harvard Key (OIDC) and stores all data in DynamoDB.

## Organization
```
your-project/                    # Parent directory with your e11 package
├── pyproject.toml              # Defines how to install the e11 package
├── e11/                        # Your Python package
│   ├── __init__.py
│   └── (other e11 modules)
└── lambda-home/                # Your Lambda app directory
    ├── template.yaml
    └── home_app/
        ├── home.py
        ├── requirements.txt    # Contains "-e ../"
        ├── static/
        └── templates/
```

## Local Dashboard Testing with SAM

For the purpose of development and local testing, you can run the dashboard locally using AWS SAM (Serverless Application Model). This allows you to test changes without deploying to AWS, while still connecting to real AWS services like DynamoDB.

### Prerequisites
- Docker Desktop installed
- AWS SAM CLI: `brew install aws-sam-cli`
- Java: `brew install openjdk`
- Poetry installed: `brew install poetry`

### Steps

```bash
# 1. Authenticate with AWS SSO
AWS_REGION=us-east-2 AWS_PROFILE=e11-staff aws sso login

# 2. Start Docker Desktop (must be running before SAM commands)
open -a Docker

# 3. Generate requirements.txt
cd /path/to/e11-spring26-dev/etc/e11-cli/lambda-home
poetry run pip freeze | grep -v "^-e " | grep -v "^e11==" > src/requirements.txt

# 4. Build SAM application
sam build --use-container

# 5. Start DynamoDB Local (in a new terminal)
cd /path/to/e11-spring26-dev/etc/e11-cli
make start_local_dynamodb

# 6. AWS creds to container and start local API (back in lambda-home)
cd /path/to/e11-spring26-dev/etc/e11-cli/lambda-home
sam local start-api --profile e11-staff
```

## Testing

See [tests/README.md](tests/README.md) for comprehensive test documentation.

Quick start:
```bash
# Start DynamoDB Local (from etc/e11-cli directory)
make start_local_dynamodb

# Run tests (from lambda-home directory)
poetry run pytest tests/ -v
```

The test suite includes 91 tests covering OIDC authentication, registration API, dashboard routing, grading queue, and utility functions.
