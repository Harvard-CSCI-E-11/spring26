import argparse
import sys


class DummyScanTable:
    def __init__(self, items):
        self._items = items

    def scan(self, **_kwargs):
        return {"Items": list(self._items)}


def test_student_report_parser_routes_debug_flag(monkeypatch):
    from e11.e11admin import cli, staff

    called = {}

    def fake_handler(args):
        called["debug"] = args.debug
        called["email"] = args.email

    monkeypatch.setattr(staff, "do_student_report", fake_handler)
    monkeypatch.setattr(sys, "argv", ["e11admin", "student-report", "--debug", "--email", "student@example.edu"])

    cli.main()
    assert called == {"debug": True, "email": "student@example.edu"}


def test_student_report_suppresses_raw_items_without_debug(monkeypatch, capsys):
    from e11.e11admin import staff

    items = [{
        "user_id": "user-123",
        "sk": "#",
        "preferred_name": "Student Example",
        "email": "student@example.edu",
        "user_registered": 1775332800,
        "claims": {"name": "Student Example"},
    }]

    monkeypatch.setattr(staff.boto3.session, "Session", lambda: type("Session", (), {"profile_name": "test"})())
    monkeypatch.setattr(staff, "dynamodb_client", type("Client", (), {
        "list_tables": lambda self: {"TableNames": ["e11-users"]},
        "describe_table": lambda self, TableName: {"Table": {"ItemCount": len(items)}},
    })())
    monkeypatch.setattr(staff, "dynamodb_resource", type("Resource", (), {
        "Table": lambda self, _name: DummyScanTable(items),
    })())

    staff.do_student_report(argparse.Namespace(email=None, dump=False, debug=False))

    out = capsys.readouterr().out
    assert "Student Example" in out
    assert "{'preferred_name': 'Student Example'" not in out


def test_student_report_prints_raw_items_with_debug(monkeypatch, capsys):
    from e11.e11admin import staff

    items = [{
        "user_id": "user-123",
        "sk": "#",
        "preferred_name": "Student Example",
        "email": "student@example.edu",
        "user_registered": 1775332800,
        "claims": {"name": "Student Example"},
    }]

    monkeypatch.setattr(staff.boto3.session, "Session", lambda: type("Session", (), {"profile_name": "test"})())
    monkeypatch.setattr(staff, "dynamodb_client", type("Client", (), {
        "list_tables": lambda self: {"TableNames": ["e11-users"]},
        "describe_table": lambda self, TableName: {"Table": {"ItemCount": len(items)}},
    })())
    monkeypatch.setattr(staff, "dynamodb_resource", type("Resource", (), {
        "Table": lambda self, _name: DummyScanTable(items),
    })())

    staff.do_student_report(argparse.Namespace(email=None, dump=False, debug=True))

    out = capsys.readouterr().out
    assert '"preferred_name": "Student Example"' in out


def test_student_report_selected_student_header_and_claim_email_fallback(monkeypatch, capsys):
    from e11.e11admin import staff, student_selector

    items = [{
        "user_id": "user-123",
        "sk": "#",
        "preferred_name": "Preferred Student",
        "email": "primary@example.edu",
        "user_registered": 1775332800,
        "claims": {
            "email": "student@g.harvard.edu",
            "email_verified": True,
            "name": "Student Example",
            "preferred_username": "g.harvard.edu",
            "sub": "abc123",
        },
    }]

    monkeypatch.setattr(staff.boto3.session, "Session", lambda: type("Session", (), {"profile_name": "test"})())
    monkeypatch.setattr(staff, "dynamodb_client", type("Client", (), {
        "list_tables": lambda self: {"TableNames": ["e11-users"]},
        "describe_table": lambda self, TableName: {"Table": {"ItemCount": len(items)}},
    })())
    monkeypatch.setattr(student_selector, "users_table", DummyScanTable(items))
    monkeypatch.setattr(staff, "dynamodb_resource", type("Resource", (), {
        "Table": lambda self, _name: DummyScanTable(items),
    })())

    staff.do_student_report(argparse.Namespace(email="student@g.harvard.edu", user_id=None, dump=False, debug=False))

    out = capsys.readouterr().out
    assert "Student:" in out
    assert "Name" in out
    assert "Student Example" in out
    assert "Email" in out
    assert "primary@example.edu" in out
    assert "user_id" in out
    assert "user-123" in out
    assert "claims.preferred_username" in out
    assert "g.harvard.edu" in out
    assert "claims.email_verified" in out
    assert "True" in out


def test_student_report_rejects_invalid_email_selector(capsys):
    from e11.e11admin import student_selector

    try:
        student_selector.student_user(argparse.Namespace(email="g.harvard.edu", user_id=None))
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("invalid --email value should exit")

    err = capsys.readouterr().err
    assert "--email requires a full email address" in err
    assert "Use --user-id" in err
