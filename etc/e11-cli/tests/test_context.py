import json

from pathlib import Path
from e11.e11core.context import build_ctx, chdir_to_lab
from e11.e11core import constants
from e11.e11core.utils import get_logger

logger = get_logger("e11-test")

def test_ctx_and_dns_and_chdir(_isolate_env,tmp_path):
    logger.error("tmp_path=%s",tmp_path)
    ctx = build_ctx("lab0")
    assert ctx["lab"] == "lab0"
    assert ctx["smashedemail"] == "testexample"
    assert ctx["labdns"] == "testexample-lab0.csci-e-11.org"
    chdir_to_lab(ctx)
    assert Path.cwd() == (constants.COURSE_ROOT / "lab0")
