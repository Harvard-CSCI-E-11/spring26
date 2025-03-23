import socket
from healthcheck.testlib import testcase

@testcase(name="IP Address", description="Check if system has non-loopback IP address")
def test_ip_address():
    ip = socket.gethostbyname(socket.gethostname())
    if ip.startswith("127."):
        raise AssertionError(f"Only loopback IP found: {ip}")
