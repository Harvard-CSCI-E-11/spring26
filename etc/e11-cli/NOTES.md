Programmer Notes:
=================

Packaging Lessons
-----------------
* aws sam wants you to have your application be a full-blown packaged python application. Follow this layout:

```
e11-cli/                        # Contains pyproject.toml
├── pyproject.toml              # Defines the e11 package
├── e11/                        # The actual package source
│   ├── __init__.py
│   └── (other modules)
└── lambda-home/
    ├── pyproject.toml          # pyproject.toml for the lambda-home app
    ├── template.yaml           # AWS SAM template file. Note that it uses python3.13 as a BuildMethod, which automatically uses the requirements.txt file
    └── Makefile                # Makefile that builds and publishes lambda-home
    └── build/                  # build directory; not archived
    └── src/                    # python source code for lambda-home
    │   └── home_app/           # source code for the app
    │   │   └── static/         # static files for website
    │   │   └── templates/      # jinja2 files for websites
    │   └── requirements.txt    # requirements.txt for the build_app - used when building for Lambda
    │                           # Auto-generated from ../../pyproject.toml
    └── tests/                  # tests for lambda-home
```


The `sam build` would not include the requirements unless the `samconfig.toml` file contained this line:
```
    template_file = ".aws-sam/build/template.yaml"
```

Verifying the ZIP file
----------------------
To verify the ZIP file, download it from AWS:

```
PHYS=$(aws cloudformation list-stack-resources --stack-name e11-home --region us-east-1 \
      --query "StackResourceSummaries[?LogicalResourceId=='E11HomeFunction'].PhysicalResourceId" --output text)
URL=$(aws lambda get-function --function-name "$PHYS" --region us-east-1 --query 'Code.Location' --output text)
curl -sSL "$URL" -o /tmp/lambda.zip
unzip -l /tmp/lambda.zip | grep -i 'jinja2/' | head
```

We were thrown off becuase the default AWS environment contained `boto3` but it did not contain `jinja2`.

Lambdas
-------

Here’s the “mental model” of SAM’s flow — think of it as a pipeline:
```
[ Your Source Template ]
template.yaml
   |
   |  (sam build)
   v
[ SAM Build Step ]
- Installs Python deps (from requirements.txt)
- Copies your code into .aws-sam/build/<FunctionName>/
- Rewrites CodeUri to point at those build artifacts
   |
   v
[ Built Template ]
.aws-sam/build/template.yaml
   |
   |  (sam deploy --template-file .aws-sam/build/template.yaml)
   v
[ CloudFormation ]
- Uploads build artifacts to S3
- Provisions/updates resources
- Creates Lambda ZIP with code + site-packages
   |
   v
[ Running Lambda ]
- /var/task includes your code + vendored deps
- Runtime already has boto3, etc.
```



Open Quetions
=============
- What happens if the user registers under a different email then is in HarvardKey?
