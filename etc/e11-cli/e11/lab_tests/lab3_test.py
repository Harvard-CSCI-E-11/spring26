import re
from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import assert_contains, assert_not_contains, assert_len_between, TestFail
from e11.e11core.context import build_ctx

@timeout(5)
def test_venv_present( tr:TestRunner):
    # Require .venv exists (python_entry enforces; we also check explicitly)
    r = tr.run_command("test -x .venv/bin/python")
    if r.exit_code != 0:
        raise TestFail(".venv missing (expected .venv/bin/python)")

@timeout(5)
def test_nginx_config_syntax_ok( tr:TestRunner):
    r = tr.run_command("sudo nginx -t")
    if r.exit_code != 0:
        raise TestFail("nginx -t failed", context=r.stderr)

@retry(times=3, backoff=0.25)
@timeout(10)
def test_https_root_ok( tr:TestRunner):
    ctx = build_ctx("lab3")
    url = f"https://{ctx['labdns']}/"
    r = tr.http_get(url, tls_info=True)
    if r.status != 200:
        raise TestFail(f"Expected 200 at {url}, got {r.status}", context=r.headers)
    assert_contains(r.text, re.compile(r"welcome\s+to\s+lab\s*3", re.I), context=3)

@timeout(5)
def test_backdoor_ssh_on_port_80_closed( tr:TestRunner ):
    ctx = build_ctx("lab3")
    if tr.port_check(ctx["public_ip"], 80):
        raise TestFail("TCP/80 accepted a connection (SSH backdoor likely active)")

@timeout(5)
def test_nginx_site_conf_no_autoindex( tr:TestRunner):
    txt = tr.read_file("/etc/nginx/sites-enabled/lab3.conf")
    assert_not_contains(txt, r"autoindex\s+on\s*;", flags=re.I, context=3)
    assert_len_between(txt, min_len=100, max_len=100_000)

@timeout(5)
def test_python_entry_returns_ok( tr:TestRunner):
    res = tr.python_entry(file="lab3_app.py", func="entry_point", args=("smoke",), venv=".venv")
    if res.exit_code != 0:
        raise TestFail("entry_point exited non-zero", context=res.stderr)
    got = res.value if res.value is not None else res.stdout.strip()
    if got != "OK":
        raise TestFail(f"Expected 'OK', got '{got}'", context=res.stdout)
