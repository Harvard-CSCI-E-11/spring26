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
    └── Makefile                # Makefile that builds and publishes lambda-home
    └── src/                    # python source code for lambda-home
    │   └── home_app/           # source code for the app
    │   └── requirements.txt    # requirements.txt for the build_app - used when installed on lambda.
    │                           # Auto-generated from ../../pyproject.toml
    └── tests/                  # tests for lambda-home



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
