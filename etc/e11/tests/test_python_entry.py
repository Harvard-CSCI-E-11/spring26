from pathlib import Path
from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core.primitives import python_entry
from e11.e11core.assertions import TestFail

def test_python_entry_ok(tmp_path):
    ctx = build_ctx("lab0")
    chdir_to_lab(ctx)

    # Fake venv presence
    venv = Path(".venv") / "bin"
    venv.mkdir(parents=True)
    (venv / "python").write_text("#!/bin/sh\n", encoding="utf-8")

    # Simple module to call
    Path("lab0_app.py").write_text(
        "def entry_point(arg):\n"
        "    return 'OK' if arg=='smoke' else 'BAD'\n", encoding="utf-8"
    )

    res = python_entry("lab0_app.py", "entry_point", args=("smoke",), venv=".venv")
    assert res.exit_code == 0
    assert res.value == "OK"
