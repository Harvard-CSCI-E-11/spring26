import os
from pathlib import Path
from . import constants
from .config import E11Config

def build_ctx(lab: str) -> dict:
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
        "lab": lab,             # "lab3"
        "labnum": labnum,       # 3
        "course_root": str(constants.COURSE_ROOT),
        "labdir": str(labdir),  # "/home/ubuntu/spring26/lab3"
        "labdns": labdns,       # "smashedemail-lab3.csci-e-11.org"
        "course_key": cfg.course_key, # per-student
        "email": cfg.email,           # per-student
        "smashedemail": cfg.smashedemail, # per-student
        "public_ip": cfg.public_ip        # per vm
    }
    return ctx

def chdir_to_lab(ctx):
    Path(ctx["labdir"]).mkdir(parents=True, exist_ok=True)
    os.chdir(ctx["labdir"])
