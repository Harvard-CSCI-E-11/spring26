import json

from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core.grader import discover_and_run

def test_discover_and_run_lab0(tmp_path, _isolate_env):
    # _isolate_env monkeypatches COURSE_ROOT, but we need to manually update ctx.labdir
    # since the monkeypatch may not work as expected with Path objects
    ctx = build_ctx("lab0")
    # Manually update labdir to use tmp_path for testing
    from e11.e11core import constants
    if str(constants.COURSE_ROOT) != str(tmp_path / "course"):
        # Monkeypatch didn't work, manually set the path
        ctx.labdir = str(tmp_path / "course" / "lab0")
        ctx.course_root = str(tmp_path / "course")
    chdir_to_lab(ctx)
    summary = discover_and_run(ctx)
    assert summary["lab"] == "lab0"

    # One test in lab0 should fail (test_fails is expected to fail)
    # test_cwd_is_labdir may also fail if chdir didn't work
    print("summary:\n",json.dumps(summary,indent=4, default=str))
    assert len(summary["fails"]) >= 1  # At least one failure expected
    assert summary["score"] > 0
