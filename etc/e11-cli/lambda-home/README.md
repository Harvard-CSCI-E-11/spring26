Organization:
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
