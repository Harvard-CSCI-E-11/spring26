# e11admin - E11 Admin CLI Tool

This is the admin tool for E11 faculty to run on their desktop computers.
It is not designed for use by students.

## Installation

`e11admin` is installed as part of the main `e11` package. It is available as a CLI command
after installing the e11 package:

```bash
# Install the e11 package (which includes e11admin)
cd /path/to/e11-cli
poetry install

# Run e11admin commands
poetry run e11admin <command>
```

## Usage

The `e11admin` command provides staff-only administrative functions for managing
the E11 course infrastructure. It is installed as a Poetry script entry point
alongside the main `e11` command.

The `AWS_PROFILE` variable must be set to an AWS Profile that has read/write access to the appropriate DynamoDB tables.

To see available commands:
```bash
poetry run e11admin --help
```

## Development

To lint the e11admin code, use the main project's linting tools:
```bash
cd /path/to/e11-cli
poetry run pylint e11/e11admin
poetry run pyright e11/e11admin
```

See the main project README and ARCHITECTURE.md for more information about the e11 package structure.
