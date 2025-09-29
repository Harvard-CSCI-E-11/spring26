# e11.lab_tests.lab1_test
import re
import socket

from e11.e11core.decorators import timeout, retry
from e11.e11core.testrunner import TestRunner
from e11.e11core.assertions import TestFail, assert_contains


# The exact line we expect in authorized_keys
AUTO_GRADER_KEY_LINE = (
    "ssh-ed25519 "
    "AAAAC3NzaC1lZDI1NTE5AAAAIEK/6zvwwWOO+ui4zbUYN558g+LKh5N8f3KpoyKKrmoR "
    "auto-grader-do-not-delete"
)

def _tcp_peek_banner(host: str, port: int, timeout_s: float = 2.0, nbytes: int = 64) -> str:
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

@timeout(2)
def test_hostname( tr:TestRunner ):
    """
    See if the hostname program works
    """
    r = tr.run_command("hostname")
    if r.exit_code !=0:
        raise TestFail("hostname command does not work")
    return r.stdout


@timeout(2)
def test_journal_retension( tr:TestRunner):
    """
    check if the journal retains for 6 months
    """
    try:
        txt = tr.read_file("/etc/systemd/journald.conf")
    except Exception as e:  # pragma: no cover - surfaced to student clearly
        raise TestFail(f"Cannot read /etc/systemd/journald.conf")
    for line in txt.split("\n"):
        if line.strip()=="MaxRetentionSec=6month":
            return "MaxRetentionSec set to '6month' in /etc/systemd/journald.conf"
    raise TestFail(f"MaxRetentionSec not set to '6month' in /etc/systemd/journald.conf")


@retry(times=3, backoff=0.25)
@timeout(5)
def test_no_ssh_on_port_80( tr:TestRunner ):
    """
    Ensure port 80 is not an SSH server (no 'SSH-' banner).
    In local 'check' we peek 127.0.0.1:80; in grader we peek the VM's public IP:80.
    """
    host = tr.ctx.get("public_ip","127.0.0.1")
    banner = _tcp_peek_banner(host, 80, timeout_s=2.0)
    if banner.startswith("SSH-"):
        raise TestFail(f"SSH banner detected on {host}:80", context=banner[:80])

@timeout(5)
def test_ssh80_service_inactive_and_disabled( tr:TestRunner ):
    """
    ssh80.service should not be running and should be disabled (or not present).
    """
    # is-active: expect NOT 'active'
    r_active = tr.run_command("sudo systemctl is-active ssh80")
    status = r_active.stdout.strip()
    if status == "active":
        raise TestFail("ssh80.service is active", context=r_active.stdout or r_active.stderr)

    # is-enabled: expect 'disabled' or 'masked'; 'not-found' also acceptable
    r_enabled = tr.run_command("sudo systemctl is-enabled ssh80")
    enabled_out = (r_enabled.stdout or "").strip()
    enabled_err = (r_enabled.stderr or "").strip()
    ok_states = {"disabled", "masked"}
    if enabled_out not in ok_states and "not-found" not in enabled_err.lower():
        raise TestFail(
            "ssh80.service is not disabled",
            context=(enabled_out or enabled_err) or "(no output)"
        )

@timeout(5)
def test_hacker_user_deleted( tr:TestRunner ):
    """
    The 'hacker' user should not exist.
    """
    r = tr.run_command("id -u hacker")
    if r.exit_code == 0:
        raise TestFail("User 'hacker' still exists", context=r.stdout or r.stderr)

@timeout(5)
def test_autograder_key_present( tr:TestRunner ):
    """
    The autograder key must exist in ubuntu's authorized_keys.
    """
    auth_path = "/home/ubuntu/.ssh/authorized_keys"
    try:
        txt = tr.read_file(auth_path)
    except Exception as e:  # pragma: no cover - surfaced to student clearly
        raise TestFail(f"Cannot read {auth_path}", context=str(e)) from e
    # Require the exact key line (comment is part of it)
    assert_contains(txt, re.escape(AUTO_GRADER_KEY_LINE))
