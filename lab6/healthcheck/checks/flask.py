import http.client
import socket
from healthcheck.config import LAB_HTTP_PORT
from healthcheck.testlib import testcase

@testcase(name="HTTP Server Listening", description="Check if HTTP server is running and returns HTML")
def test_http_server():
    try:
        conn = http.client.HTTPConnection("localhost", LAB_HTTP_PORT, timeout=3)
        conn.request("GET", "/")
        response = conn.getresponse()
        content_type = response.getheader("Content-Type", "")
        body = response.read().decode(errors="replace")
        conn.close()

        if response.status != 200:
            raise AssertionError(f"HTTP status {response.status} instead of 200")

        if "text/html" not in content_type:
            raise AssertionError(f"Unexpected Content-Type: {content_type}")

        if "<html" not in body.lower():
            raise AssertionError("Body does not appear to be HTML")

        return f"HTTP 200 OK with Content-Type {content_type}"

    except (ConnectionRefusedError, socket.timeout) as e:
        raise AssertionError(f"Could not connect to localhost:{LAB_HTTP_PORT} - {e}")
    except Exception as e:
        raise AssertionError(f"HTTP request failed: {e}")
