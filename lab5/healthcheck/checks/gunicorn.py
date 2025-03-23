import subprocess
from healthcheck.testlib import testcase

@testcase(name="Gunicorn Running", description="Check if Gunicorn process is active")
def test_gunicorn_running():
    out = subprocess.check_output(["ps", "aux"], text=True)
    if "gunicorn" not in out:
        raise AssertionError("Gunicorn is not running")
