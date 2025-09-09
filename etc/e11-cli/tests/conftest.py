import os
from pathlib import Path
import pytest

TEST_CONFIG="""
[student]
preferred_name=Preferred Name
email=test@example.org
smashedemail=testexampleorg
public_ip=127.0.0.1
course_key=key1234
"""

@pytest.fixture(autouse=True)
def _isolate_env(tmp_path, monkeypatch):
    # Fake HOME with a minimal ~/e11-config.ini
    fake_home = tmp_path / "home"
    monkeypatch.setenv("HOME", str(fake_home))

    fake_home.mkdir()
    cfg = fake_home / "e11-config.ini"
    cfg.write_text(TEST_CONFIG, encoding="utf-8")

    # Redirect COURSE_ROOT to tmp to avoid touching the real FS
    from e11.e11core import constants
    monkeypatch.setattr(constants, "COURSE_ROOT", tmp_path / "course", raising=False)
    (tmp_path / "course").mkdir()

    yield
