# Coding Standards

This document is the canonical source for repository-wide coding standards.

## Core Rules

- Keep code clean, correct, and current.
- When code changes, update the relevant documentation and meaningful tests in the same change.
- Prefer direct imports from the canonical module that owns a behavior or type.
- Do not add compatibility layers, shim layers, or re-export wrappers just to preserve an older local import path.
- Do not create duplicate source modules with the same filename in different directories. If two modules do different jobs, they need different names.

## Package Boundaries

- Shared code belongs in `src/common/`.
- Robot-only code belongs in `src/robot_app/`.
- Web-only code belongs in `src/web_app/`.
- Code that needs shared schemas should import `common.schema` directly. Do not create `robot_app.schema`, `web_app.schema`, or similar alias modules.
- Do not add dependencies from `robot_app` to `web_app`, or from `web_app` to `robot_app`.

## Testing

- Tests must check real logic or behavior. Do not add pro-forma tests that only inflate coverage.
- If a behavior cannot yet be tested meaningfully, it is better to leave it untested than to add a bogus test.
- Avoid mocking unless it is genuinely necessary and there is no practical real-test alternative.
- Prefer local real-service tests over mocks:
  - DynamoDB tests use DynamoDB Local.
  - S3 tests use local MinIO.
- Keep tests up to date with the code they cover. Out-of-date tests are a defect, not an asset.

## Commands And Workflows

- Use the `Makefile` as the contract for build, test, validation, and deployment workflows.
- Do not introduce parallel one-off command paths in the documentation when a `make` target is the supported workflow.
- For Lambda/runtime-sensitive Python code, keep the AWS-like validation path in `make pytest-lambda`.

## Documentation

- Keep documentation aligned with the code that actually runs.
- Remove stale migration notes once the migration is complete.
- Do not document temporary compatibility behavior as if it were part of the intended architecture.
