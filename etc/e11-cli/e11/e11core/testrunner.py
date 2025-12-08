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
import traceback
import sys
import json

import urllib.parse
from urllib.request import build_opener, Request
from urllib.error import HTTPError,URLError


from dataclasses import dataclass
from typing import Optional
from .constants import DEFAULT_NET_TIMEOUT_S,DEFAULT_HTTP_TIMEOUT_S
from .assertions import TestFail  # for nice errors in grader mode
from .context import E11Context
from .e11ssh import E11Ssh
from .utils import get_logger, get_error_location

LOGGER = get_logger("testrunner")

@dataclass
class CommandResult:
    exit_code: int
    stdout: str
    stderr: str
    text: str  # alias for stdout
    def json(self):
        return json.loads(self.stdout or "")

@dataclass
class HTTPResult:
    status: int
    headers: str
    text: str
    content: bytes | None
    cert: dict | None = None

    def json(self):
        return json.loads(self.content or "")

@dataclass
class PythonEntryResult:
    exit_code: int
    stdout: str
    stderr: str
    value: object | None = None

class TestRunner:
    def __init__(self, ctx: E11Context, ssh:Optional[E11Ssh] = None):
        """
        :param ctx: E11Context object
        :param ssh: if True, use ssh. as the mechanism
        """
        self.ssh = ssh
        self.ctx : E11Context = ctx

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
            LOGGER.debug("read_file SSH %s",path)
            try:
                data = self.ssh.sftp_read(path).decode("utf-8", "replace")
                LOGGER.debug("read %s bytes",len(data))
                return data
            except Exception as e:   # pylint: disable=broad-exception-caught
                rc, out, err = self.ssh.exec(f"sudo -n /bin/cat -- {shlex.quote(path)}", timeout=DEFAULT_NET_TIMEOUT_S)
                if rc != 0:
                    raise TestFail(f"cannot read {path} (rc={rc})", context=err) from e
                return out

        LOGGER.debug("read_file %s",path)
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # pylint: disable=too-many-locals, disable=too-many-positional-arguments, disable=too-many-statements
    def http_get(self,
                 url: str, handler=None, tls_info=True, method='GET',
                 data=None, headers=None,
                 timeout=DEFAULT_HTTP_TIMEOUT_S) -> HTTPResult:

        # Get from HTTP. This should work from anywhere
        LOGGER.debug("http_get %s timeout %s",url,timeout)
        content = None
        headers_txt = ""
        if handler:
            opener = build_opener(handler)
        else:
            opener = build_opener()
        req = Request(url, method=method, data=data, headers=headers or {})
        try:
            with opener.open(req, timeout=timeout) as r:
                status = r.getcode()
                headers_txt = "".join(f"{k}: {v}\n" for k, v in r.headers.items())
                content = r.read()
                text = content.decode("utf-8", errors="replace")
        except HTTPError as e:
            status = e.code
            if e.headers:
                if isinstance(e.headers, dict):
                    headers_txt = "".join(f"{k}: {v}\n" for k, v in e.headers.items())
                else:
                    headers_txt = str(e.headers)
            text = e.read().decode("utf-8", errors="replace") if e.fp else ""
        except URLError as e:   # more general
            # Get traceback information for detailed logging
            exc_type, exc_value, exc_traceback = sys.exc_info()

            # Find the line number in the test file where http_get was called
            filename, line_no = get_error_location(exc_traceback, exclude_pattern='testrunner.py')

            # Log detailed error information
            error_details = f"URL: {url}, Error: {e}"
            if filename != "unknown" and line_no != "unknown":
                error_details += f", File: {filename}, Line: {line_no}"
            LOGGER.info("http_get failed: %s", error_details)

            # Log the traceback itself?
            tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
            tb_str = "".join(tb_lines)
            LOGGER.debug("http_get Traceback:\n====== START OF TRACEBACK=======\n%s\n=========END OF TRACEBACK=========", tb_str)
            status = 0

            # Include detailed error information in the text for user reporting
            error_text = f"HTTP request failed - URL: {url}, Error: {e}"
            if filename != "unknown" and line_no != "unknown":
                error_text += f", File: {filename}, Line: {line_no}"
            text = error_text

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
        return HTTPResult(status=status, headers=headers_txt, content=content, text=text, cert=cert_info)

    def port_check(self, host: str, port: int, timeout=3) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
