# Coding Standards

This document is the canonical source for repository-wide coding standards.

## Core Rules

- Keep code clean, correct, and current.
- When code changes, update the relevant documentation and meaningful tests in the same change.
- Prefer direct imports from the canonical module that owns a behavior or type.
- Do not add compatibility layers, shim layers, or re-export wrappers just to preserve an older local import path.
- Do not create duplicate source modules with the same filename in different directories. If two modules do different jobs, they need different names.

## Package Boundaries

- Shared CLI and Lambda code belongs in the root `e11/` package.
- Student-facing CLI behavior belongs in `e11/main.py`, `e11/support.py`, and `e11/e11core/`.
- Staff-only administrative behavior belongs in `e11/e11admin/`.
- Lambda dashboard behavior belongs in `lambda-home/src/home_app/`.
- Lambda leaderboard behavior belongs in `lambda-leaderboard/src/leaderboard_app/`.
- The Lambda projects consume `e11/` through the vendored `e11.whl`; do not edit vendored wheel contents directly.
- Keep component-specific logic inside its component. If shared behavior is needed by both CLI and Lambda code, put it in `e11/` and re-vend the wheel through the Makefile workflow.

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
- For repo-wide validation, use `make check-all`.
- For component validation, use `make check` from the component directory.
- For Lambda code, keep `vend-e11` in the validation and deployment path so the packaged runtime sees the current shared `e11/` code.

## Documentation

- Keep documentation aligned with the code that actually runs.
- Remove stale migration notes once the migration is complete.
- Do not document temporary compatibility behavior as if it were part of the intended architecture.
