"""
Primitives for the grading systems.
Tests must be able to run locally when the user types `e11 check lab1` or remotely (from the server) when the user requests a grading with `e11 grade lab1`

CommandResult - Object that includes exit_code, stdout, stderr, and text (alias for stdout)
run_command(str, timeout) -> CommandResult - runs either locally or by ssh depending on if called by check or grade.
"""


import io
import os
import re
import ssl
import socket
import subprocess
import sys
import traceback
import json
import shlex
import importlib.util

from urllib.request import HTTPRedirectHandler, build_opener, Request
from urllib.error import HTTPError
from urllib.parse import urlparse


from dataclasses import dataclass
from typing import Optional
from .constants import DEFAULT_NET_TIMEOUT_S
from .assertions import TestFail  # for nice errors in grader mode
from .e11ssh import E11Ssh

@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    text: str  # alias for stdout

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

class TestRunner:
    def __init__(self, ctx:dict, ssh:Optional[E11Ssh] = None):
        """
        :param ssh: if True, use ssh. as the mechanism
        """
        self.ssh = ssh
        self.ctx = ctx

    def run_command(self, cmd: str, timeout=DEFAULT_NET_TIMEOUT_S) -> CommandResult:
        if self.ssh:
            rc, out, err = self.ssh.exec(cmd, timeout=timeout)
            return CommandResult(rc, out, err, out)

        p = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = p.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            p.kill(); out, err = p.communicate()
            return CommandResult(124, out, err, out)
        return CommandResult(p.returncode, out, err, out)

    def read_file(self, path: str) -> str:
        # grader: SFTP first, sudo-catat fallback
        if self.ssh:
            try:
                data = self.ssh.sftp_read(path)
                return data.decode("utf-8", "replace")
            except Exception:
                rc, out, err = self.ssh.exec(f"sudo -n /bin/cat -- {shlex.quote(path)}", timeout=DEFAULT_NET_TIMEOUT_S)
                if rc != 0:
                    raise TestFail(f"cannot read {path} (rc={rc})", context=err)
                return out

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    def http_get(self, url: str, tls_info=True, timeout=DEFAULT_NET_TIMEOUT_S) -> HTTPResult:
        # Get from HTTP. THis should work from anywhere
        opener = build_opener()
        req = Request(url, method="GET")
        try:
            with opener.open(req, timeout=timeout) as r:
                status = r.getcode()
                headers = "".join(f"{k}: {v}\n" for k, v in r.headers.items())
                text = r.read().decode("utf-8", errors="replace")
        except HTTPError as e:
            status = e.code
            headers = "".join(f"{k}: {v}\n" for k, v in (e.headers or {}).items())
            text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        cert_info = None
        if tls_info and url.lower().startswith("https://"):
            import urllib.parse
            host = urllib.parse.urlparse(url).hostname
            if host:
                ctx = ssl.create_default_context()
                with socket.create_connection((host, 443), timeout=timeout) as sock:
                    with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                        cert_info = {}
                        pc = ssock.getpeercert()
                        if pc:
                            cert_info = {
                                "subject": pc.get("subject"),
                                "issuer": pc.get("issuer"),
                                "dns_names": [v for k, v in pc.get("subjectAltName", []) if k == "DNS"],
                            }
        return HTTPResult(status=status, headers=headers, text=text, cert=cert_info)

    def port_check(self, host: str, port: int, timeout=3) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0

    def python_entry(self, file: str, func: str, args=(), kwargs=None, venv=".venv", timeout=DEFAULT_NET_TIMEOUT_S) -> PythonEntryResult:
        kwargs = kwargs or {}

        if self.ssh:
            # grader: run remotely using the student's Python; print JSON sentinel
            py = ".venv/bin/python" if venv else "python3"
            args_js = json.dumps(list(args))
            kwargs_js = json.dumps(kwargs)
            script = f"""
        import importlib.util, json, sys
        spec = importlib.util.spec_from_file_location("student_entry", {repr(file)})
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        fn = getattr(mod, {repr(func)})
        val = fn(*json.loads({repr(args_js)}), **json.loads({repr(kwargs_js)}))
        print("__E11_VALUE__="+json.dumps(val))
        """
            rc, out, err = self.ssh.exec(f"{py} - <<'PY'\n{script}\nPY", timeout=timeout)
            value = None
            m = re.search(r"__E11_VALUE__=(.*)", out)
            if m:
                try:
                    value = json.loads(m.group(1))
                except Exception:
                    pass
            return PythonEntryResult(exit_code=rc, stdout=out, stderr=err, value=value)

        # local: import and call directly, capturing stdout/err
        old_out, old_err = sys.stdout, sys.stderr
        buf_out, buf_err = io.StringIO(), io.StringIO()
        sys.stdout, sys.stderr = buf_out, buf_err
        exit_code = 0; value = None
        try:
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
        except Exception:
            exit_code = 1
            traceback.print_exc()
        finally:
            sys.stdout.flush(); sys.stderr.flush()
            out, err = buf_out.getvalue(), buf_err.getvalue()
            sys.stdout, sys.stderr = old_out, old_err
        return PythonEntryResult(exit_code=exit_code, stdout=out, stderr=err, value=value)
