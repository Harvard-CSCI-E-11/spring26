import subprocess
import socket
import ssl
from cryptography import x509
from cryptography.hazmat.backends import default_backend


from healthcheck.testlib import testcase
from healthcheck.config import COURSE_DOMAIN,COURSE_NAME,DOT_COURSE_DOMAIN,LAB_NAME

LOCALHOST = "127.0.0.1"
LAB_HOSTNAME = socket.gethostname().replace(DOT_COURSE_DOMAIN,"-"+LAB_NAME+DOT_COURSE_DOMAIN)

@testcase(name=f'{COURSE_NAME} Hostname set', description='Check to make sure hostname was properly set')
def test_hostname_set():
    hostname = socket.gethostname()
    if not hostname.endswith("." + COURSE_DOMAIN):
        raise AssertionError(f"hostname {hostname} is not in the {COURSE_DOMAIN} domain")

@testcase(name=f'{LAB_HOSTNAME} has valid DNS', description='Check to make sure hostname for this lab has proper DNS')
def test_ip_matches_hostname():
    try:
        dns = socket.gethostbyname(LAB_HOSTNAME)
    except socket.gaierror as e:
        raise AssertionError(f"DNS resolution failed: {e}")

    public_ip = subprocess.check_output(['curl','http://checkip.amazonaws.com','--silent'], text=True).strip()
    if dns != public_ip:
        raise AssertionError(f"public IP address {public_ip} does not match DNS IP {dns} for {LAB_HOSTNAME}")


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

@testcase(name="HTTPS Cert", description="Check if certificate contains correct SAN for lab")
def test_https_cert():
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

        with socket.create_connection((LOCALHOST, 443), timeout=3) as sock:
            with context.wrap_socket(sock, server_hostname=LOCALHOST) as ssock:
                der_cert = ssock.getpeercert(binary_form=True)

        cert = x509.load_der_x509_certificate(der_cert, default_backend())
        san = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName)
        dns_names = san.value.get_values_for_type(x509.DNSName)

        if LAB_HOSTNAME not in dns_names:
            raise AssertionError(f"Expected {LAB_HOSTNAME} in SANs: {dns_names}")

        return "TLS certificate names: "+str(sorted(dns_names))

    except Exception as e:
        raise AssertionError(f"Failed to validate cert: {e}")
