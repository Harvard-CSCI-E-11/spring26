import configparser
import os
from pathlib import Path

CONFIG_PATH = Path.home() / ".e11-config.ini"

class E11Config:
    def __init__(self):
        self.email = None
        self.smashedemail = None
        self.public_ip = None
        self.shared_secret = None

    @classmethod
    def load(cls):
        cfg = cls()
        if not CONFIG_PATH.exists():
            return cfg
        p = configparser.ConfigParser()
        p.read(CONFIG_PATH)
        s = p["e11"] if "e11" in p else p["DEFAULT"]
        cfg.email = s.get("email")
        cfg.smashedemail = s.get("smashedemail")
        cfg.public_ip = s.get("public_ip")
        cfg.shared_secret = s.get("shared_secret", fallback=None)
        return cfg
