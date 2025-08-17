from pathlib import Path
from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core import constants

def test_ctx_and_dns_and_chdir(tmp_path):
    ctx = build_ctx("lab0")
    assert ctx["lab"] == "lab0"
    assert ctx["smashedemail"] == "testexampleorg"
    assert ctx["labdns"] == "testexampleorg-lab0.csci-e-11.org"
    chdir_to_lab(ctx)
    assert Path.cwd() == (constants.COURSE_ROOT / "lab0")
