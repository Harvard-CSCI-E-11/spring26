import socket
from healthcheck.testlib import testcase

@testcase(name="DNS Resolution", description="Check if google.com resolves correctly")
def test_dns_resolution():
    try:
        socket.gethostbyname("google.com")
    except socket.gaierror as e:
        raise AssertionError(f"DNS resolution failed: {e}")
