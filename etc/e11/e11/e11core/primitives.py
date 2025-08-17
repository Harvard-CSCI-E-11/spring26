import importlib.util
import io
import socket
import ssl
import subprocess
import sys
import traceback
import urllib.request
from dataclasses import dataclass
from typing import Optional

from .constants import DEFAULT_NET_TIMEOUT_S

@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    text: str  # alias to stdout

@dataclass
class HTTPResult:
    status: int
    headers: str
    text: str
    cert: Optional[dict] = None

@dataclass
class PythonEntryResult:
    exit_code: int
    stdout: str
    stderr: str
    value: Optional[object] = None

def run_command(cmd: str, timeout=DEFAULT_NET_TIMEOUT_S) -> CommandResult:
    p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        p.kill()
        out, err = p.communicate()
        return CommandResult(exit_code=124, stdout=out, stderr=err, text=out)
    return CommandResult(exit_code=p.returncode, stdout=out, stderr=err, text=out)

def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def http_get(url: str, follow_redirects=True, tls_info=True, timeout=DEFAULT_NET_TIMEOUT_S) -> HTTPResult:
    class _NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k): return None
    opener = urllib.request.build_opener(None if follow_redirects else _NoRedirect)
    req = urllib.request.Request(url, method="GET")
    try:
        with opener.open(req, timeout=timeout) as r:
            status = r.getcode()
            headers = "".join(f"{k}: {v}\n" for k, v in r.headers.items())
            text = r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        status = e.code
        headers = "".join(f"{k}: {v}\n" for k, v in e.headers.items()) if e.headers else ""
        text = e.read().decode("utf-8", errors="replace") if e.fp else ""
    cert_info = None
    if tls_info and url.lower().startswith("https://"):
        try:
            host = urllib.request.urlparse.urlparse(url).hostname  # type: ignore[attr-defined]
        except Exception:
            import urllib.parse
            host = urllib.parse.urlparse(url).hostname
        port = 443
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                pc = ssock.getpeercert()
                cert_info = {
                    "subject": pc.get("subject"),
                    "issuer": pc.get("issuer"),
                    "dns_names": pc.get("subjectAltName", []),
                }
    return HTTPResult(status=status, headers=headers, text=text, cert=cert_info)

def port_check(host: str, port: int, timeout=3) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(timeout)
        res = s.connect_ex((host, port))
        return res == 0

def python_entry(file: str, func: str, args=(), kwargs=None, venv=".venv") -> PythonEntryResult:
    kwargs = kwargs or {}
    # capture stdout/err
    old_out, old_err = sys.stdout, sys.stderr
    buf_out, buf_err = io.StringIO(), io.StringIO()
    sys.stdout, sys.stderr = buf_out, buf_err
    exit_code = 0
    value = None
    try:
        # require venv presence (path exists with bin/python)
        import os
        if venv and not (os.path.isdir(venv) and os.path.isfile(f"{venv}/bin/python")):
            raise RuntimeError(f"virtualenv '{venv}' not found (expected {venv}/bin/python)")

        spec = importlib.util.spec_from_file_location("student_entry", file)
        if not spec or not spec.loader:
            raise RuntimeError(f"cannot import {file}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[attr-defined]
        fn = getattr(mod, func)
        value = fn(*args, **kwargs)
    except SystemExit as e:
        exit_code = int(e.code) if isinstance(e.code, int) else 1
    except Exception:  # noqa: BLE001
        exit_code = 1
        traceback.print_exc()
    finally:
        sys.stdout.flush(); sys.stderr.flush()
        out, err = buf_out.getvalue(), buf_err.getvalue()
        sys.stdout, sys.stderr = old_out, old_err
    return PythonEntryResult(exit_code=exit_code, stdout=out, stderr=err, value=value)
