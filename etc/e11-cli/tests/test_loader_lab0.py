import json

from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core.grader import discover_and_run

def test_discover_and_run_lab0(tmp_path, _isolate_env):
    # _isolate_env monkeypatches COURSE_ROOT to tmp_path/course; build_ctx uses it for local runs
    ctx = build_ctx("lab0")
    chdir_to_lab(ctx)
    summary = discover_and_run(ctx)
    assert summary["lab"] == "lab0"

    # One test in lab0 should fail (test_fails is expected to fail)
    # test_cwd_is_labdir may also fail if chdir didn't work
    print("summary:\n",json.dumps(summary,indent=4, default=str))
    assert len(summary["fails"]) >= 1  # At least one failure expected
    assert summary["score"] > 0
