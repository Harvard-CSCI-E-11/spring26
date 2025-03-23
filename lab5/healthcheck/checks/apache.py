import subprocess
import socket
import ssl
from healthcheck.testlib import testcase

HOSTNAME = "example.com"

@testcase(name="Apache Running", description="Check if Apache process is running")
def test_apache_running():
    out = subprocess.check_output(["ps", "aux"], text=True)
    if "apache2" not in out and "httpd" not in out:
        raise AssertionError("Apache is not running")

@testcase(name="HTTPS Port", description="Check if Apache is listening on port 443")
def test_https_port():
    try:
        with socket.create_connection(("localhost", 443), timeout=2):
            pass
    except Exception as e:
        raise AssertionError(f"Port 443 not open: {e}")

@testcase(name="HTTPS Cert", description="Check if certificate matches given hostname")
def test_https_cert():
    try:
        context = ssl.create_default_context()
        with socket.create_connection((HOSTNAME, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=HOSTNAME) as ssock:
                cert = ssock.getpeercert()
                subject_alt_names = [v for k, v in cert.get('subjectAltName', []) if k == 'DNS']
                if HOSTNAME not in subject_alt_names:
                    raise AssertionError(f"Cert does not match hostname: {subject_alt_names}")
    except Exception as e:
        raise AssertionError(f"Failed to validate cert: {e}")
