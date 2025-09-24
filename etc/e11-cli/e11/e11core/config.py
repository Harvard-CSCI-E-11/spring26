import configparser
from pathlib import Path
from .constants import CONFIG_FILENAME
from .utils import smash_email

class E11Config:                # pylint: disable=too-few-public-methods
    """Access to variables in the E11 config file,
    automatically resolving HOME at runtime to handle mocking."""
    def __init__(self):
        self.config_path = Path.home() / CONFIG_FILENAME
        self.course_key = None
        self.email = None
        self.public_ip = None
        self.smashedemail = None

    @classmethod
    def load(cls):
        cfg = cls()
        if not cfg.config_path.exists():
            return cfg
        p = configparser.ConfigParser()
        p.read(cfg.config_path)
        s = p["student"] if "student" in p else p["DEFAULT"]
        cfg.course_key   = s.get("course_key", fallback=None)
        cfg.email        = s.get("email", fallback=None)
        cfg.public_ip    = s.get("public_ip", fallback=None)
        cfg.smashedemail = smash_email(s.get("email", fallback=""))
        return cfg
