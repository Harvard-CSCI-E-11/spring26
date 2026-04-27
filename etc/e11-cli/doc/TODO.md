# TODO

This backlog is ranked by ease of addressing, not by severity. Items marked
`done` were fixed in the cleanup that created this document; remaining items
need follow-up changes.

## Review Findings, Ranked By Ease

1. `done` Fix wrong e11 package paths in documentation.
   - Replaced stale `e11/staff.py` references with `e11/e11admin/staff.py`.
   - Replaced copied coding-standards package boundaries with e11-specific boundaries.

2. `done` Remove stale direct test-command documentation.
   - Updated `TESTING.md`, `TESTING_STRATEGY.md`, and Lambda README files to point at Makefile workflows.
   - Removed stale moto language from `TESTING.md`.

3. `done` Make `lambda-leaderboard` production deploy run checks.
   - `lambda-leaderboard/Makefile` now makes `prod-vbd` depend on `lint` and `check` instead of echoing those commands.

4. `done` Fix the non-executing registration integration test.
   - `lambda-home/tests/test_e11_registration_integration.py` now patches `e11.main`, runs `do_register()`, and asserts the captured request payload.

5. `done` Make the root grading email test independent of the calendar date.
   - `tests/test_main_commands.py` now pins the Lambda API clock to before the configured lab deadline instead of failing after `lab6` closes.

6. `todo` Replace fake S3 tests with MinIO-backed tests.
   - `lambda-home/tests/conftest.py` still provides `FakeS3`.
   - Production code uses presigned uploads, `head_object`, and `delete_object`; tests should exercise those paths against local MinIO where practical.

7. `todo` Stop mocking DynamoDB persistence in the SQS grading flow.
   - `lambda-home/tests/test_queue_grade.py` still replaces `add_user_log` and `add_grade` with no-ops.
   - The test should write real log and grade records to DynamoDB Local, then assert stored state.

## Additional Technical Debt To Address

1. `easy` Remove obsolete scratch files.
   - `e11/e11admin/attack_student_instances.py-broken`
   - `e11/e11core/test_runner_python_entry.xxx`
   - `tests/test_python_entry.xxx`

2. `easy` Decide whether `lambda-home/notes.md` belongs in version control.
   - It contains an old production AccessDenied note. Move durable information into docs or delete it.

3. `easy` Replace `ruff check --fix` in `lambda-home/Makefile` lint.
   - A lint/check target should report drift, not mutate files. Add a separate formatting target if auto-fix is wanted.

4. `easy` Keep pylint-compatible subprocess tests without hiding behavior.
   - `e11/e11admin/staff.py` currently disables `consider-using-with` for the interactive SSH process so Ctrl-C handling remains directly testable.
   - A cleaner follow-up would wrap the teardown behavior in a small helper that can be tested without monkeypatching `subprocess.Popen`.

5. `easy` Make coverage numbers either generated or remove them.
   - `TESTING.md` and `doc/CODE_ISSUES_FIXED.md` contain fixed historical coverage numbers that will drift.

6. `medium` Move admin report/status tests onto DynamoDB Local.
   - `tests/test_e11admin_student_report.py`, `tests/test_e11admin_student_log.py`, and parts of `tests/test_e11admin_status.py` still use dummy tables or patched helper functions where real DynamoDB Local records would be clearer.

7. `medium` Improve Lambda runtime-fidelity in tests.
   - Lambda test `pythonpath` includes both `../` and vendored `e11.whl`, so most tests can import live source instead of proving the packaged wheel behavior.
   - Keep import-validation tests, but add at least one runtime-shaped smoke path that imports only from the vendored wheel.

8. `medium` Replace module-level boto3 clients with explicit client construction seams.
   - `e11/e11_common.py`, `e11/e11admin/cli.py`, and Lambda modules create AWS clients at import time.
   - This makes local endpoint selection and test isolation rely on import ordering and monkeypatching.

9. `medium` Fix session expiry handling for malformed records.
   - `lambda-home/src/home_app/sessions.py::expire_batch` raises `TypeError` if `session_expire` is present but `None`.
   - There is already a test comment documenting this as a known production bug.

10. `medium` Remove debug API responses that expose process environment.
   - `lambda-home/src/home_app/api.py` returns `dict(os.environ)` from `ping` and `ping-mail`.
   - Even if secrets are usually not present, this is broader diagnostic exposure than a public-ish status API should provide.

11. `medium` Normalize project tooling.
   - The repo has Poetry configuration and lock files plus a root `uv.lock`.
   - Decide whether Poetry remains canonical for this repo or migrate deliberately; do not leave mixed tooling unexplained.

12. `hard` Build a practical SSH integration fixture.
   - Current SSH tests appropriately mock subprocess behavior, but grading and access flows still lack a real local SSH boundary.
   - A local container or test SSH server would make more of the grading path testable without reaching student VMs.

13. `hard` Add MinIO-backed image upload end-to-end coverage.
   - A complete test should request a presigned upload, upload an object to MinIO, invoke the S3 callback path, verify the DynamoDB image record, then delete and verify both DynamoDB and S3 state.
