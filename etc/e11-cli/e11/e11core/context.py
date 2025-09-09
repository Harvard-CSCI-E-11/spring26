import os
from pathlib import Path
from . import constants
from .config import E11Config

def build_ctx(lab: str):
    """Creates a ctx that works equally well when run locally (e11 check lab) or from the grader."""
    if not lab.startswith("lab"):
        raise ValueError("lab must be like 'lab3'")
    labnum = int(lab[3:])
    labdir = Path(constants.COURSE_ROOT) / constants.LAB_DIR_PATTERN.format(n=labnum)
    cfg = E11Config.load()
    labdns = None
    if cfg.smashedemail:
        labdns = f"{cfg.smashedemail}-{lab}.csci-e-11.org"

    ctx = {
        "version": constants.VERSION,
        "lab": lab,
        "labnum": labnum,
        "course_root": str(constants.COURSE_ROOT),
        "labdir": str(labdir),
        "labdns": labdns,
        "course_key": cfg.course_key,
        "mode": os.environ.get("E11_MODE", "local"),  # 'local' or 'grader'
        "email": cfg.email,
        "smashedemail": cfg.smashedemail,
        "public_ip": cfg.public_ip,
    }
    return ctx

def chdir_to_lab(ctx):
    Path(ctx["labdir"]).mkdir(parents=True, exist_ok=True)
    os.chdir(ctx["labdir"])
