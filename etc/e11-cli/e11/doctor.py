from pathlib import Path
from .e11core import constants
from .e11core.config import E11Config

def run_doctor(_):
    ok = True
    cfg = E11Config.load()
    print("e11 doctor:")

    if cfg.config_path.exists():
        print(f"  ✔ ${cfg.config_path} exists")
        if not cfg.email:
            ok = False
            print( "  ✘ ~/e11-config.ini missing cfg.email")
        else:
            print(f"  ✔ ~/e11-config.ini defines email: {cfg.email}")
        if not cfg.public_ip:
            ok = False
            print( "  ✘ ~/e11-config.ini missing cfg.public_ip")
        else:
            print(f"  ✔ ~/e11-config.ini defines public_ip: {cfg.public_ip}")
    else:
        ok = False
        print(f"  ✘ ${cfg.config_path} does not exist")



    if not Path(constants.COURSE_ROOT).exists():
        ok = False
        print(f"  ✘ missing course root {constants.COURSE_ROOT}")
    else:
        print(f"  ✔ course root present: {constants.COURSE_ROOT}")
    print("  ✔ python ok")
    return 0 if ok else 1
