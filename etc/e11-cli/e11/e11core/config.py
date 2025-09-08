import configparser, os, re
from pathlib import Path

CONFIG_FILENAME = "e11-config.ini"

class E11Config:
    """Access to variables in the E11 config file, automatically resolving HOME at runtime to handle mocking."""
    def __init__(self):
        self.email = None
        self.smashedemail = None
        self.public_ip = None
        self.shared_secret = None

    @classmethod
    def load(cls):
        cfg = cls()
        config_path = Path.home() / CONFIG_FILENAME
        if not config_path.exists():
            return cfg
        p = configparser.ConfigParser()
        p.read(config_path)
        s = p["student"] if "student" in p else p["DEFAULT"]
        cfg.email = s.get("email")
        cfg.smashedemail = s.get("smashedemail")
        cfg.public_ip = s.get("public_ip")
        cfg.shared_secret = s.get("shared_secret", fallback=None)
        return cfg
