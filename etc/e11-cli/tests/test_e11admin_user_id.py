import sys


USER_ID = "3c139e61-4932-4f2d-910d-fe8a5fc1741d"


def _parse_to_handler(monkeypatch, argv, handler_name):
    from e11.e11admin import cli, staff

    called = {}

    def fake_handler(args):
        called.update(vars(args))

    monkeypatch.setattr(staff, handler_name, fake_handler)
    monkeypatch.setattr(sys, "argv", ["e11admin", *argv])

    assert cli.main() == 0
    return called


def test_student_log_accepts_user_id_alias(monkeypatch):
    called = _parse_to_handler(
        monkeypatch,
        ["student-log", "--user-id", USER_ID, "lab2", "--verbose"],
        "do_student_log",
    )

    assert called["email"] is None
    assert called["user_id"] == USER_ID
    assert called["lab"] == "lab2"
    assert called["verbose"] is True


def test_student_log_accepts_user_id_underscore_alias(monkeypatch):
    called = _parse_to_handler(
        monkeypatch,
        ["student-log", "--user_id", USER_ID, "lab2"],
        "do_student_log",
    )

    assert called["email"] is None
    assert called["user_id"] == USER_ID
    assert called["lab"] == "lab2"


def test_print_grades_accepts_user_id(monkeypatch):
    called = _parse_to_handler(
        monkeypatch,
        ["print-grades", "--user-id", USER_ID, "--all"],
        "do_print_grades",
    )

    assert called["whowhat"] is None
    assert called["user_id"] == USER_ID
    assert called["all"] is True


def test_force_grade_accepts_user_id(monkeypatch):
    called = _parse_to_handler(
        monkeypatch,
        ["force-grade", "--user-id", USER_ID, "lab2", "instructor@example.edu"],
        "force_grades",
    )

    assert called["email"] is None
    assert called["user_id"] == USER_ID
    assert called["lab"] == "lab2"
    assert called["who"] == "instructor@example.edu"


def test_ssh_accepts_user_id(monkeypatch):
    called = _parse_to_handler(monkeypatch, ["ssh", "--user-id", USER_ID], "ssh_access")

    assert called["email"] is None
    assert called["user_id"] == USER_ID


def test_edit_email_accepts_user_id(monkeypatch):
    called = _parse_to_handler(
        monkeypatch,
        ["edit-email", "--user-id", USER_ID, "--alt", "alt@example.edu"],
        "do_edit_email",
    )

    assert called["email"] is None
    assert called["user_id"] == USER_ID
    assert called["alt"] == "alt@example.edu"
