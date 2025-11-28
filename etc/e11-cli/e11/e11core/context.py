"""
E11 Context - typed object for passing context to graders.
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Any
from . import constants
from .config import E11Config


@dataclass
class E11Context:  # pylint: disable=too-many-instance-attributes
    """Typed context object passed to graders and test runners."""
    # Core lab info
    version: str
    lab: str  # e.g., "lab3"
    labnum: int  # e.g., 3
    course_root: str
    labdir: str  # e.g., "/home/ubuntu/spring26/lab3"
    labdns: Optional[str] = None  # e.g., "smashedemail-lab3.csci-e-11.org"

    # Student info
    course_key: Optional[str] = None
    email: Optional[str] = None
    smashedemail: Optional[str] = None
    public_ip: Optional[str] = None

    # Grading info (set during grading)
    grade_with_ssh: bool = False
    pkey_pem: Optional[str] = None
    key_filename: Optional[str] = None

    # API Keys
    api_key: Optional[str] = None
    api_secret_key: Optional[str] = None
    database_fname : Optional[str] = None

    # Dynamic fields (for lab-specific data)
    _extra: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        """Allow dict-like access for backward compatibility."""
        if hasattr(self, key):
            return getattr(self, key)
        return self._extra.get(key)

    def __setitem__(self, key: str, value: Any) -> None:
        """Allow dict-like assignment for backward compatibility."""
        if hasattr(self, key) and not key.startswith('_'):
            setattr(self, key, value)
        else:
            self._extra[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        """Dict-like get method."""
        if hasattr(self, key):
            return getattr(self, key)
        return self._extra.get(key, default)


def build_ctx(lab: str) -> E11Context:
    """Creates a ctx that works equally well when run locally (e11 check lab) or from the grader."""
    if not lab.startswith("lab"):
        raise ValueError("lab must be like 'lab3'")
    labnum = int(lab[3:])
    labdir = Path(constants.COURSE_ROOT) / constants.LAB_DIR_PATTERN.format(n=labnum)
    cfg = E11Config.load()
    labdns = None
    if cfg.smashedemail:
        labdns = f"{cfg.smashedemail}-{lab}.{constants.DOMAIN}"

    return E11Context(
        version=constants.VERSION,
        lab=lab,
        labnum=labnum,
        course_root=str(constants.COURSE_ROOT),
        labdir=str(labdir),
        labdns=labdns,
        course_key=cfg.course_key,
        email=cfg.email,
        smashedemail=cfg.smashedemail,
        public_ip=cfg.public_ip
    )


def chdir_to_lab(ctx: E11Context) -> None:
    """Change directory to the lab directory."""
    labdir_path = Path(ctx.labdir)
    # Create the directory if it doesn't exist
    if not labdir_path.exists():
        labdir_path.mkdir(parents=True, exist_ok=True)
    # Change to the lab directory
    os.chdir(ctx.labdir)
