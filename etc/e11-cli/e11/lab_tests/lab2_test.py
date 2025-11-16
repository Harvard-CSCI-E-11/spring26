"""
lab2 tester
"""

import tempfile
import urllib
import urllib.request

import crossplane               # type: ignore

# pylint: disable=unused-import
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail, assert_contains

STUDENT_USER = 'student'
STUDENT_AUTH = 'secret'

def get_nginx_servers(tr):
    servers = set()
    try:
        text = tr.read_file("/etc/nginx/sites-available/default")
    except Exception as e:  # pragma: no cover - surfaced to student clearly
        raise TestFail("Cannot read /etc/nginx/sites-available/default") from e
    wrapped = f"http {{\n{text}\n}}\n"

    with tempfile.NamedTemporaryFile(mode='w+') as tf:
        tf.write(wrapped)
        tf.seek(0)
        data =  crossplane.parse(tf.name)
    if data['status'] != 'ok':
        raise TestFail("Crossplane cannot parse /etc/nginx/sites-available/default")
    for config in data['config']: # pylint: disable=too-many-nested-blocks
        if config['status'] != 'ok':
            raise TestFail("nginx sites file config status is not okay")
        for parsed in config['parsed']:
            if parsed['directive']=='http':
                for http_block in parsed['block']:
                    if http_block['directive']=='server':
                        for server_block in http_block['block']:
                            if server_block['directive']=='server_name':
                                for arg in server_block['args']:
                                    servers.add(arg)
    return servers

def get_cert_organization(cert):
    for tpl in cert['issuer']:
        for (k,v) in tpl:
            if k=='organizationName':
                return v
    return None

def domain(tr):
    return f"{tr.ctx['smashedemail']}.csci-e-11.org"

@timeout(2)
def test_hostname( tr:TestRunner ):
    """
    See if the hostname program works
    """
    r = tr.run_command("hostname")
    if r.exit_code !=0:
        raise TestFail("hostname command does not work")
    return r.stdout


def test_nginx( tr:TestRunner ):
    """
    See if the nginx program is installed
    """
    servers = get_nginx_servers(tr)
    d = domain(tr)
    if d not in servers:
        raise TestFail(f"{d} not in nginx config file")
    return f"{d} in nginx config file"

def test_home( tr:TestRunner ):
    """
    See if the home certificate is installed.
    """
    d = domain(tr)
    url = f"https://{d}/"
    r = tr.http_get(url, tls_info=True)
    if r.status != 200:
        raise TestFail(f"could not read {url}. certificate: {r.cert}")
    org = get_cert_organization(r.cert)
    if org!="Let's Encrypt":
        raise TestFail(f"TLS certificate issued by {org} and not Let's Encrypt")
    return f"Successfully read {url}. Certificate is valid from Let's Encrypt"

def test_public( tr:TestRunner ):
    """
    See if the hostname program works
    """
    d = domain(tr)
    url = f"https://{d}/public.html"
    r = tr.http_get(url, tls_info=False)
    if r.status != 200:
        raise TestFail(f"could not read {url}")
    return f"Successfully read {url}."

def test_confidential_no_password( tr:TestRunner ):
    """
    See if the hostname program works
    """
    d = domain(tr)
    url = f"https://{d}/confidential.html"
    r = tr.http_get(url, tls_info=False)
    if r.status == 200:
        raise TestFail(f"No password protection on {url}")
    if 400 <= r.status <= 499:
        return f"Received HTTP error 404 attempting to read {url} without a password"
    raise TestFail(f"Error attempting to access {url} status={r.status}")

def test_confidential_password( tr:TestRunner ):
    """
    See if the hostname program works
    """
    password_mgr = urllib.request.HTTPPasswordMgrWithDefaultRealm()
    d = domain(tr)
    top_level_url = f"https://{d}/confidential/"
    password_mgr.add_password(None, top_level_url, STUDENT_USER, STUDENT_AUTH)
    handler = urllib.request.HTTPBasicAuthHandler(password_mgr)

    url = top_level_url + "confidential.html"
    r = tr.http_get(url, handler=handler)
    if r.status != 200:
        raise TestFail(f"Could not access {url} with username '{STUDENT_USER}' password '{STUDENT_AUTH}'")
    return f"Correctly accessed {url} with {STUDENT_USER}/{STUDENT_AUTH}"
