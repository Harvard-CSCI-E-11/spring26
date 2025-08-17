import os
from pathlib import Path
from .constants import COURSE_ROOT
from .config import E11Config

def run_doctor():
    ok = True
    cfg = E11Config.load()
    print("e11 doctor:")
    if not cfg.email or not cfg.smashedemail:
        ok = False
        print("  ✘ ~/.e11-config.ini missing [email/smashedemail]")
    else:
        print(f"  ✔ email: {cfg.email} smashed: {cfg.smashedemail}")
    if not Path(COURSE_ROOT).exists():
        ok = False
        print(f"  ✘ missing course root {COURSE_ROOT}")
    else:
        print(f"  ✔ course root present: {COURSE_ROOT}")
    print("  ✔ python ok")
    return 0 if ok else 1
