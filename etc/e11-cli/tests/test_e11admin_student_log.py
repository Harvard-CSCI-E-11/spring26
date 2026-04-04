import argparse
import json
import sys
import subprocess


class DummyTable:
    def __init__(self, items):
        self._items = items

    def query(self, **_kwargs):
        return {"Items": list(self._items)}


def _patch_admin_query(monkeypatch, items):
    from e11.e11admin import staff

    monkeypatch.setattr(staff, "users_table", DummyTable(items))
    fake_user = type(
        "User",
        (),
        {
            "user_id": "user-123",
            "email": "student@example.edu",
            "public_ip": "13.60.16.99",
            "host_registered": 1775332800,
        },
    )()
    monkeypatch.setattr(
        staff,
        "get_user_from_email",
        lambda email: fake_user,
    )
    monkeypatch.setattr(staff, "_resolve_primary_dns", lambda fqdn: "13.60.16.99")
    monkeypatch.setattr(
        staff.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], 0, stdout="PING ok\n5 packets transmitted", stderr=""
        ),
    )
    return staff


def _grade_item(user_id, lab, timestamp, score, *, passes=None, fails=None, note=""):
    passes = passes or []
    fails = fails or []
    summary = {
        "lab": lab,
        "passes": passes,
        "fails": fails,
        "tests": (
            [{"name": name, "status": "pass", "message": f"{name} ok"} for name in passes] +
            [{"name": name, "status": "fail", "message": f"{name} failed"} for name in fails]
        ),
        "score": score,
        "message": "",
        "ctx": {"public_ip": "127.0.0.1"},
        "error": False,
    }
    item = {
        "user_id": user_id,
        "sk": f"grade#{lab}#{timestamp}",
        "lab": lab,
        "public_ip": "127.0.0.1",
        "score": str(score),
        "pass_names": passes,
        "fail_names": fails,
        "raw": json.dumps(summary),
    }
    if note:
        item["note"] = note
    return item


def _log_item(user_id, timestamp, message):
    return {
        "user_id": user_id,
        "sk": f"log#{timestamp}",
        "message": message,
    }


def test_student_log_parser_routes_to_handler(monkeypatch):
    from e11.e11admin import cli, staff

    called = {}

    def fake_handler(args):
        called["email"] = args.email
        called["lab"] = args.lab
        called["verbose"] = args.verbose

    monkeypatch.setattr(staff, "do_student_log", fake_handler)
    monkeypatch.setattr(sys, "argv", ["e11admin", "student-log", "student@example.edu", "lab2", "--verbose"])

    assert cli.main() == 0
    assert called == {"email": "student@example.edu", "lab": "lab2", "verbose": True}


def test_student_log_summary_table(monkeypatch, capsys):
    staff = _patch_admin_query(monkeypatch, [
        _log_item(
        "user-123",
        "2026-04-01T09:00:00.000000",
        "User registered instanceId=i-123 public_ip=13.62.54.213",
        ),
        _grade_item(
        "user-123",
        "lab1",
        "2026-02-01T10:00:00.000000",
        "2.5",
        passes=["test_a"],
        fails=["test_b"],
        ),
        _grade_item(
        "user-123",
        "lab1",
        "2026-02-03T12:30:00.000000",
        "5.0",
        passes=["test_a", "test_b"],
        ),
        _grade_item(
        "user-123",
        "lab2",
        "2026-02-05T09:15:00.000000",
        "4.0",
        passes=["test_c", "test_d"],
        fails=["test_e"],
        ),
    ])

    staff.do_student_log(argparse.Namespace(email="student@example.edu", lab=None, verbose=False))

    out = capsys.readouterr().out
    assert "Primary DNS:" in out
    assert "Ping command:" in out
    assert "ping -c 5 " in out
    assert "5 packets transmitted" in out
    assert "csci-e-11.org" in out
    assert "current A record" in out
    assert "13.60.16.99" in out
    assert "IP history:" in out
    assert "13.62.54.213" in out
    assert "13.60.16.99" in out
    assert "registration log" in out
    assert "user record" in out
    assert "lab" in out
    assert "sessions" in out
    assert "lab1" in out
    assert "lab2" in out
    assert "2026-02-01T10:00:00.000000" in out
    assert "2026-02-03T12:30:00.000000" in out
    assert "5.0" in out
    assert "4.0" in out


def test_student_log_verbose_lab_output(monkeypatch, capsys):
    staff = _patch_admin_query(monkeypatch, [
        _log_item(
        "user-123",
        "2026-04-01T09:00:00.000000",
        "User registered instanceId=i-123 public_ip=13.62.54.213",
        ),
        _grade_item(
        "user-123",
        "lab1",
        "2026-02-01T10:00:00.000000",
        "3.5",
        passes=["test_hostname"],
        fails=["test_nginx"],
        note="manual retry",
        ),
    ])

    staff.do_student_log(argparse.Namespace(email="student@example.edu", lab="lab1", verbose=True))

    out = capsys.readouterr().out
    assert "Primary DNS:" in out
    assert "Ping command:" in out
    assert "IP history:" in out
    assert "lab1:" in out
    assert "student ip" in out
    assert "127.0.0.1" in out
    assert "manual retry" in out
    assert "=== lab1 grading run 2026-02-01T10:00:00.000000 ===" in out
    assert '"test_hostname"' in out
    assert "=== lab1 Results ===" in out
    assert "Score: 3.5 / 5.0" in out
