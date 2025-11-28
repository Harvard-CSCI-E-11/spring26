import logging
import functools
import os
import re
import socket

@functools.cache                # singleton
def _configure_root_once():
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Configure a dedicated app logger; avoid touching the root logger.
    app_logger = logging.getLogger("e11")
    app_logger.setLevel(level)

    if not app_logger.handlers:
        handler = logging.StreamHandler()
        fmt = "%(asctime)s %(levelname)s [%(name)s %(filename)s:%(lineno)d %(funcName)s] %(message)s"
        handler.setFormatter(logging.Formatter(fmt))
        app_logger.addHandler(handler)

    # Prevent bubbling to root (stops double logs)
    app_logger.propagate = False

    # If this code is used as a library elsewhere, avoid “No handler” warnings:
    logging.getLogger(__name__).addHandler(logging.NullHandler())

def get_logger(name: str | None = None) -> logging.Logger:
    """Get a logger under the 'e11' namespace (e.g., e11.grader)."""
    _configure_root_once()
    return logging.getLogger("e11" + ("" if not name else f".{name}"))

def smash_email(email):
    """Convert an email into the CSCI E-11 smashed email"""
    email    = re.sub(r'[^-a-zA-Z0-9_@.+]', '', email).lower().strip()
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
