import subprocess
from os.path import dirname
from healthcheck.testlib import testcase
from healthcheck.config import INSTALL_DIR

MY_INSTALL_DIR = dirname(dirname(dirname(__file__)))
MY_GUNICORN    = INSTALL_DIR + '/venv/bin/gunicorn'

@testcase(name='Install dir', description='Check to make sure installed in correct directory')
def test_install_dir():
    if MY_INSTALL_DIR != INSTALL_DIR:
        raise AssertionError(f"Installed in {MY_INSTALL_DIR} and not {INSTALL_DIR}")


@testcase(name="Gunicorn Running", description="Check if Gunicorn process is active")
def test_gunicorn_running():
    out = subprocess.check_output(["ps", "aux"], text=True)
    if MY_GUNICORN not in out:
        raise AssertionError("Gunicorn is not running")
