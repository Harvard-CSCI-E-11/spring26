import argparse


class DummyUserTable:
    def __init__(self, items):
        self._items = items

    def scan(self, **_kwargs):
        return {"Items": list(self._items)}


def test_run_interactive_ssh_returns_child_exit_code(monkeypatch):
    from e11.e11admin import staff

    class FakeProc:
        def wait(self, timeout=None):
            assert timeout is None
            return 7

    monkeypatch.setattr(staff.subprocess, "Popen", lambda cmd, env=None: FakeProc())

    rc = staff._run_interactive_ssh(["ssh", "ubuntu@example"], env={"A": "B"})

    assert rc == 7


def test_run_interactive_ssh_terminates_on_ctrl_c(monkeypatch, capsys):
    from e11.e11admin import staff

    class FakeProc:
        def __init__(self):
            self.wait_calls = 0
            self.terminated = False

        def wait(self, timeout=None):
            self.wait_calls += 1
            if self.wait_calls == 1:
                raise KeyboardInterrupt
            assert timeout == 5
            return 130

        def terminate(self):
            self.terminated = True

    fake_proc = FakeProc()
    monkeypatch.setattr(staff.subprocess, "Popen", lambda cmd, env=None: fake_proc)

    rc = staff._run_interactive_ssh(["ssh", "ubuntu@example"], env={"A": "B"})

    out = capsys.readouterr().out
    assert rc == 130
    assert fake_proc.terminated is True
    assert "Disconnecting SSH session." in out


def test_ssh_access_exits_with_helper_return_code(monkeypatch):
    from e11.e11admin import staff, student_selector

    monkeypatch.setattr(staff, "update_path", lambda: (None, type("Api", (), {"get_pkey_pem": lambda self, name: "KEY"})()))
    monkeypatch.setattr(staff, "find_secret", lambda name: "secret-id")
    monkeypatch.setattr(staff, "smash_email", lambda email: "studentexampleedu")
    monkeypatch.setattr(student_selector, "users_table", DummyUserTable([{
        "user_id": "user-123",
        "sk": "#",
        "email": "student@example.edu",
    }]))
    monkeypatch.setattr(
        staff.subprocess,
        "run",
        lambda *args, **kwargs: type("Result", (), {"stdout": "SSH_AUTH_SOCK=/tmp/agent.sock; export SSH_AUTH_SOCK;\nSSH_AGENT_PID=1234; export SSH_AGENT_PID;\n"})(),
    )

    class FakeSshAddProc:
        returncode = 0

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def communicate(self, input=None):
            return ("", "")

    monkeypatch.setattr(staff.subprocess, "Popen", lambda *args, **kwargs: FakeSshAddProc())
    monkeypatch.setattr(staff, "_run_interactive_ssh", lambda cmd, env: 9)
    monkeypatch.setattr(staff.os, "kill", lambda pid, sig: None)

    try:
        staff.ssh_access(argparse.Namespace(email="student@example.edu"))
    except SystemExit as exc:
        assert exc.code == 9
    else:
        raise AssertionError("ssh_access should exit with the SSH return code")
