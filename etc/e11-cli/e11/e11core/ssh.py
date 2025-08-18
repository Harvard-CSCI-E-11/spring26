import io, paramiko

_ssh = None
_sftp = None
_cwd = None

def configure(host, username="ubuntu", port=22, pkey_pem=None, timeout=10):
    """Create one SSH/SFTP session for grader mode."""
    global _ssh, _sftp
    close()
    _ssh = paramiko.SSHClient()
    _ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    pkey = None
    if pkey_pem:
        for keycls in (paramiko.RSAKey, paramiko.Ed25519Key, paramiko.ECDSAKey):
            try:
                pkey = keycls.from_private_key(io.StringIO(pkey_pem))
                break
            except Exception:
                continue
    _ssh.connect(hostname=host, port=port, username=username, pkey=pkey,
                 timeout=timeout, banner_timeout=timeout, auth_timeout=timeout)
    _sftp = _ssh.open_sftp()
    return _ssh, _sftp

def set_working_dir(path: str):
    """Remote working dir used to resolve relative paths and 'cd' before commands."""
    global _cwd
    _cwd = path

def get_connection():
    if not _ssh or not _sftp:
        raise RuntimeError("SSH not configured (grader mode)")
    return _ssh, _sftp

def _q(s: str) -> str:
    import shlex; return shlex.quote(s)

def exec(cmd: str, timeout=10):
    """Run a remote command (cd to _cwd first if set). Returns (rc, out, err)."""
    ssh, _ = get_connection()
    if _cwd:
        cmd = f"cd {_q(_cwd)} && {cmd}"
    stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
    rc = stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    return rc, out, err

def sftp_read(path: str) -> bytes:
    """Read a remote file via SFTP (relative to _cwd if not absolute)."""
    _, sftp = get_connection()
    rp = path if path.startswith("/") or not _cwd else f"{_cwd.rstrip('/')}/{path}"
    with sftp.open(rp, "r") as f:
        return f.read()

def close():
    global _ssh, _sftp, _cwd
    try:
        if _sftp: _sftp.close()
        if _ssh: _ssh.close()
    finally:
        _ssh = _sftp = None
        _cwd = None
