import argparse
import csv
import sys


def _grade_item(user_id, lab, timestamp, score):
    return {
        "user_id": user_id,
        "sk": f"grade#{lab}#{timestamp}",
        "lab": lab,
        "score": str(score),
    }


def test_status_parser_routes_to_handler(monkeypatch):
    from e11.e11admin import cli, staff

    called = {}

    def fake_handler(args):
        called["command"] = "status"

    monkeypatch.setattr(staff, "do_status", fake_handler)
    monkeypatch.setattr(sys, "argv", ["e11admin", "status"])

    cli.main()
    assert called == {"command": "status"}


def test_canvas_grades_logs_export(monkeypatch, tmp_path):
    from e11.e11admin import staff

    template = tmp_path / "template.csv"
    outfile = tmp_path / "out.csv"
    template.write_text(
        "Student,Student ID,SIS User ID,SIS Login ID,Section,Lab 1\n"
        "Points Possible,,,,,5\n"
        "\"Student, Alice\",1,,,1,\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        staff,
        "get_class_list",
        lambda: [{
            "user_id": "u1",
            "email": "alice@example.edu",
            "claims": {"name": "Alice Student"},
        }],
    )
    monkeypatch.setattr(
        staff,
        "get_items",
        lambda lab: [_grade_item("u1", lab, "2026-02-01T10:00:00.000000", "5.0")],
    )

    logged = {}

    def fake_add_admin_log(action, message, **extra):
        logged["action"] = action
        logged["message"] = message
        logged.update(extra)

    monkeypatch.setattr(staff, "add_admin_log", fake_add_admin_log)

    staff.canvas_grades(argparse.Namespace(lab="lab1", template=template, outfile=outfile))

    assert outfile.exists()
    with outfile.open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[-1][-1] == "5.0"
    assert logged["action"] == "canvas-grades"
    assert logged["lab"] == "lab1"
    assert logged["exported_count"] == 1
    assert logged["outfile"] == str(outfile)


def test_status_reports_grade_increases_since_last_canvas_export(monkeypatch, capsys):
    from e11.e11admin import staff

    monkeypatch.setattr(
        staff,
        "_admin_log_items",
        lambda: [{
            "user_id": "__e11admin__",
            "sk": "admin-log#2026-02-05T12:00:00.000000",
            "action": "canvas-grades",
            "lab": "lab1",
            "message": "Canvas grades exported for lab1",
        }],
    )
    monkeypatch.setattr(
        staff,
        "get_class_list",
        lambda: [
            {"user_id": "u1", "email": "alice@example.edu", "claims": {"name": "Alice Student"}},
            {"user_id": "u2", "email": "bob@example.edu", "claims": {"name": "Bob Student"}},
        ],
    )
    monkeypatch.setattr(
        staff,
        "get_items",
        lambda lab: [
            _grade_item("u1", lab, "2026-02-01T10:00:00.000000", "3.0"),
            _grade_item("u1", lab, "2026-02-10T10:00:00.000000", "5.0"),
            _grade_item("u2", lab, "2026-02-01T10:00:00.000000", "4.0"),
        ],
    )

    staff.do_status(argparse.Namespace())

    out = capsys.readouterr().out
    assert "lab1 since canvas-grades on 2026-02-05 12:00:00" in out
    assert "alice@example.edu" in out
    assert "3.0 -> 5.0" in out
    assert "bob@example.edu" not in out
