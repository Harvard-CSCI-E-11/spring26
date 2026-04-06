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
