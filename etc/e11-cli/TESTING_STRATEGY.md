# Testing Strategy

This document records the current test strategy for the e11 repo. The supported command interface is the Makefile; do not document direct pytest, Poetry, or ad hoc shell commands as normal workflows.

## Current Policy

- Run root CLI validation with `make check`.
- Run all components with `make check-all`.
- Run Lambda Home validation with `cd lambda-home && make check`.
- Run Lambda Leaderboard validation with `cd lambda-leaderboard && make check`.
- Use DynamoDB Local for DynamoDB behavior.
- Use local MinIO for S3 behavior where practical.
- Mock only boundaries that cannot be exercised locally without unacceptable cost or risk, such as live Route53, SES, Secrets Manager, EC2 metadata, and interactive SSH.

## Preferred Test Shapes

- CLI command tests should exercise the command function with real config files in temporary directories.
- Registration and grading tests should route through the Lambda handler or API dispatch where practical, with DynamoDB state stored in DynamoDB Local.
- Admin reporting tests should create real DynamoDB Local records, run the report code, and assert observable output.
- S3 image upload/delete tests should use MinIO instead of fake S3 clients.
- SSH process-control tests may mock subprocesses because they verify local command construction and exit behavior, not the remote SSH service.

## Known Gaps

See `doc/TODO.md` for the current ranked list of testing and technical debt.
