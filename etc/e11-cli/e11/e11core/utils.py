import logging
import functools
import os
import re
import socket

import boto3
from botocore.exceptions import ClientError

LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s %(filename)s:%(lineno)d %(funcName)s] %(message)s"

def get_log_level():
    return os.getenv("LOG_LEVEL", "INFO").upper()

def _ensure_e11_root_handler():
    """Add a single handler to the root e11 logger. Child loggers propagate to it."""
    root = logging.getLogger("e11")
    if not root.handlers:
        root.setLevel(get_log_level())
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(LOG_FORMAT))
        root.addHandler(handler)


@functools.lru_cache(maxsize=128)
def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger under the 'e11' namespace (e.g., e11.grader)."""
    _ensure_e11_root_handler()
    logger = logging.getLogger("e11" + ("" if not name else f".{name}"))
    logger.setLevel(get_log_level())
    return logger

def smash_email(email):
    """Convert an email into the CSCI E-11 smashed email.
    Remove underbars and plus signs"""
    email    = re.sub(r'[^-a-zA-Z0-9@.]', '', email).lower().strip()
    smashed_email = "".join(email.replace("@",".").split(".")[0:2])
    return smashed_email

def tcp_peek_banner(host: str, port: int, timeout_s: float = 2.0, nbytes: int = 64) -> str:
    """
    Connects to host:port, reads up to nbytes (non-blocking), returns decoded banner (may be '').
    SSH servers usually send 'SSH-2.0-...' immediately; HTTP servers send nothing until a request.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout_s) as s:
            s.settimeout(timeout_s)
            try:
                data = s.recv(nbytes)
            except socket.timeout:
                return ""
            return data.decode("utf-8", errors="ignore")
    except OSError:
        # Connection refused/timeout => definitely not an SSH banner
        return ""

def get_error_location(exc_traceback, test_file_pattern='_test.py', exclude_pattern=None):
    """
    Extract filename and line number from traceback where error occurred in test files.
    :param exc_traceback: Exception traceback object
    :param test_file_pattern: Pattern to match test files (default: '_test.py')
    :param exclude_pattern: Optional pattern to exclude (e.g., 'testrunner.py')
    :return: tuple of (filename, line_no) or ("unknown", "unknown")
    """
    line_no = "unknown"
    filename = "unknown"
    if exc_traceback:
        tb = exc_traceback
        while tb:
            frame = tb.tb_frame
            code = frame.f_code
            # Look for frames in test files
            if code.co_filename.endswith(test_file_pattern):
                if exclude_pattern and code.co_filename.endswith(exclude_pattern):
                    tb = tb.tb_next
                    continue
                line_no = tb.tb_lineno
                filename = code.co_filename.split('/')[-1]
                break
            tb = tb.tb_next
    return filename, line_no

def read_s3(bucket,key):
    s3 = boto3.client( 's3' )
    try:
        return s3.get_object( Bucket=bucket, Key=key)['Body'].read()
    except ClientError:
        return f"s3://{bucket}/{key} not found"
