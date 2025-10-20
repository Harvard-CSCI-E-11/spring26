"""
Primitives for the grading systems.
Tests must be able to run locally when the user types `e11 check lab1` or remotely (from the server) when the user requests a grading with `e11 grade lab1`

CommandResult - Object that includes exit_code, stdout, stderr, and text (alias for stdout)
run_command(str, timeout) -> CommandResult - runs either locally or by ssh depending on if called by check or grade.
"""


import ssl
import socket
import subprocess
import shlex

import urllib.parse
from urllib.request import build_opener, Request
from urllib.error import HTTPError


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

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, ex_traceback):
        if self.ssh:
            self.ssh.close()

    def run_command(self, cmd: str, timeout=DEFAULT_NET_TIMEOUT_S) -> CommandResult:
        if self.ssh:
            rc, out, err = self.ssh.exec(cmd, timeout=timeout)
            return CommandResult(rc, out, err, out)

        with subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as p:
            try:
                out, err = p.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                p.kill()
                out, err = p.communicate()
                return CommandResult(124, out, err, out)
            return CommandResult(p.returncode, out, err, out)

    def read_file(self, path: str) -> str:
        # grader: SFTP first, sudo-catat fallback
        if self.ssh:
            try:
                data = self.ssh.sftp_read(path)
                return data.decode("utf-8", "replace")
            except Exception as e:   # pylint: disable=broad-exception-caught
                rc, out, err = self.ssh.exec(f"sudo -n /bin/cat -- {shlex.quote(path)}", timeout=DEFAULT_NET_TIMEOUT_S)
                if rc != 0:
                    raise TestFail(f"cannot read {path} (rc={rc})", context=err) from e
                return out

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # pylint: disable=too-many-locals, disable=too-many-positional-arguments
    def http_get(self, url: str, handler=None, tls_info=True, method='GET', data=None, timeout=DEFAULT_NET_TIMEOUT_S) -> HTTPResult:
        # Get from HTTP. This should work from anywhere
        if handler:
            opener = build_opener(handler)
        else:
            opener = build_opener()
        req = Request(url, method=method, data=data)
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
            host = urllib.parse.urlparse(url).hostname
            if host:
                ctx = ssl.create_default_context()
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
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
