import json

from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core.grader import discover_and_run

def test_discover_and_run_lab0(tmp_path):
    ctx = build_ctx("lab0")
    chdir_to_lab(ctx)
    summary = discover_and_run(ctx)
    assert summary["lab"] == "lab0"

    # One test in lab0 should fail
    print("summary:\n",json.dumps(summary,indent=4))
    assert len(summary["fails"]) == 1
    assert summary["score"] > 0
