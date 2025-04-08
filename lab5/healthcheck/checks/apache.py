import subprocess
import socket
import ssl
from cryptography import x509
from cryptography.hazmat.backends import default_backend
import re


from healthcheck.testlib import testcase
from healthcheck.config import COURSE_DOMAIN,COURSE_NAME,DOT_COURSE_DOMAIN,LAB_NAME,LAB3_NAME,LAB4_NAME,LAB5_NAME

LOCALHOST = "127.0.0.1"
LAB3_HOSTNAME = socket.gethostname().replace(DOT_COURSE_DOMAIN,"-"+LAB3_NAME+DOT_COURSE_DOMAIN)
LAB4_HOSTNAME = socket.gethostname().replace(DOT_COURSE_DOMAIN,"-"+LAB4_NAME+DOT_COURSE_DOMAIN)
LAB5_HOSTNAME = socket.gethostname().replace(DOT_COURSE_DOMAIN,"-"+LAB5_NAME+DOT_COURSE_DOMAIN)
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

def validate_file(fname,line):
    stripped_line = re.sub(r"\s+","",line)
    with open(fname,"r") as f:
        for l2 in f:
            l2 = re.sub(r"\s+","",l2)
            if stripped_line == l2:
                return
    raise AssertionError(f"Cannot find {line} in {fname}")


@testcase(name="Lab4 Apache Conf", description="Check to make sure Apache lab4 conf is correct")
def test_lab4_http():
    validate_file("/etc/httpd/conf.d/lab4.conf",'ServerName '+LAB4_HOSTNAME)
    validate_file("/etc/httpd/conf.d/lab4.conf",'DocumentRoot /home/ec2-user/spring25/lab4/www')
    validate_file("/etc/httpd/conf.d/lab4.conf",'ProxyPass "/" "http://127.0.0.1:8004/"')
    validate_file("/etc/httpd/conf.d/lab4.conf",'ProxyPassReverse "/" "http://127.0.0.1:8004/"')

@testcase(name="Lab4 Apache SSL Conf", description="Check to make sure Apache lab4 SSL conf is correct")
def test_lab4_http():
    validate_file("/etc/httpd/conf.d/lab4-le-ssl.conf",'ServerName '+LAB4_HOSTNAME)
    validate_file("/etc/httpd/conf.d/lab4-le-ssl.conf",'DocumentRoot /home/ec2-user/spring25/lab4/www')
    validate_file("/etc/httpd/conf.d/lab4-le-ssl.conf",'ProxyPass "/" "http://127.0.0.1:8004/"')
    validate_file("/etc/httpd/conf.d/lab4-le-ssl.conf",'ProxyPassReverse "/" "http://127.0.0.1:8004/"')

@testcase(name="Lab5 Apache Conf", description="Check to make sure Apache lab5 conf is correct")
def test_lab5_http():
    validate_file("/etc/httpd/conf.d/lab5.conf",'ServerName '+LAB5_HOSTNAME)
    validate_file("/etc/httpd/conf.d/lab5.conf",'DocumentRoot /home/ec2-user/spring25/lab5/www')
    validate_file("/etc/httpd/conf.d/lab5.conf",'ProxyPass "/" "http://127.0.0.1:8005/"')
    validate_file("/etc/httpd/conf.d/lab5.conf",'ProxyPassReverse "/" "http://127.0.0.1:8005/"')

@testcase(name="Lab5 Apache SSL Conf", description="Check to make sure Apache lab5 SSL conf is correct")
def test_lab5_http():
    validate_file("/etc/httpd/conf.d/lab5-le-ssl.conf",'ServerName '+LAB5_HOSTNAME)
    validate_file("/etc/httpd/conf.d/lab5-le-ssl.conf",'DocumentRoot /home/ec2-user/spring25/lab5/www')
    validate_file("/etc/httpd/conf.d/lab5-le-ssl.conf",'ProxyPass "/" "http://127.0.0.1:8005/"')
    validate_file("/etc/httpd/conf.d/lab5-le-ssl.conf",'ProxyPassReverse "/" "http://127.0.0.1:8005/"')
