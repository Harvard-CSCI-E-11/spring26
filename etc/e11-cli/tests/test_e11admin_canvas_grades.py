import argparse
import csv
from pathlib import Path


def _make_template(tmp_path, template_names=None):
    """Create a Canvas template CSV with a single student row."""
    template_names = template_names or ["Garfinkel, Simson"]
    template = tmp_path / "template.csv"
    with template.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"])
        writer.writerow(["Points Possible", "", "", "", "", "5"])
        for index, template_name in enumerate(template_names, start=1):
            writer.writerow([
                template_name,
                f"{1000 + index}",
                f"sis-{1000 + index}",
                f"login{index}",
                "01",
                "",
            ])
    return template


def _run_canvas_grades(tmp_path, monkeypatch, roster_entries, grade_user_ids=None, template_names=None):
    """Patch staff helpers and run canvas_grades; return (output_rows, stdout)."""
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    outfile = tmp_path / "out.csv"
    template = _make_template(tmp_path, template_names=template_names)
    grade_user_ids = grade_user_ids or {entry[A.USER_ID] for entry in roster_entries}

    monkeypatch.setattr(staff, "get_class_list", lambda: roster_entries)
    monkeypatch.setattr(
        staff,
        "get_items",
        lambda lab: [
            {
                A.USER_ID: entry[A.USER_ID],
                A.SK: "grade#lab1#2026-04-06T12:00:00.000000",
                A.SCORE: "5.0",
            }
            for entry in roster_entries
            if entry[A.USER_ID] in grade_user_ids
        ],
    )
    monkeypatch.setattr(staff, "get_highest_grades", lambda items: items)

    import sys
    from io import StringIO
    captured = StringIO()
    old_stdout = sys.stdout
    sys.stdout = captured
    try:
        staff.canvas_grades(argparse.Namespace(lab="lab1", template=template, outfile=outfile))
    finally:
        sys.stdout = old_stdout

    rows = list(csv.reader(outfile.open(encoding="utf-8", newline="")))
    return rows, captured.getvalue()


def test_canvas_grades_matches_via_middle_initial_strip(tmp_path, monkeypatch):
    """Match should succeed by stripping middle initial from claims name.

    The roster entry has ``claims['name'] = "Simson L. Garfinkel"`` and a
    preferred_name that does NOT match the template.  The only path to a match
    is stripping the middle initial to produce "simson garfinkel".
    """
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    roster_entry = {
        A.USER_ID: "user-1",
        "email": "simson@example.edu",
        # preferred_name deliberately does NOT match the template
        "preferred_name": "Sim Garfinkel",
        "claims": {"name": "Simson L. Garfinkel"},
    }

    rows, out = _run_canvas_grades(tmp_path, monkeypatch, [roster_entry])

    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "login1", "01", "5.0"],
    ], "Expected match via middle-initial stripping"
    assert "Unmatched.  Will not continue" not in out


def test_canvas_grades_matches_via_preferred_name(tmp_path, monkeypatch):
    """Match should succeed via preferred_name when claims name does not match.

    The roster entry has a claims name that will never match the template even
    after middle-initial stripping.  The only path to a match is the
    ``preferred_name`` field.
    """
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    roster_entry = {
        A.USER_ID: "user-1",
        "email": "simson@example.edu",
        # preferred_name matches the template; claims name does not
        "preferred_name": "Simson Garfinkel",
        "claims": {"name": "Sim Garfinkel"},
    }

    rows, out = _run_canvas_grades(tmp_path, monkeypatch, [roster_entry])

    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "login1", "01", "5.0"],
    ], "Expected match via preferred_name"
    assert "Unmatched.  Will not continue" not in out


def test_canvas_grades_keeps_unmatched_template_students_with_zeroes(tmp_path, monkeypatch):
    """Unmatched template rows should still be written with a zero score."""
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    roster_entry = {
        A.USER_ID: "user-1",
        "email": "simson@example.edu",
        "preferred_name": "Simson Garfinkel",
        "claims": {"name": "Simson Garfinkel"},
    }

    rows, out = _run_canvas_grades(
        tmp_path,
        monkeypatch,
        [roster_entry],
        template_names=["Garfinkel, Simson", "Student, Unregistered"],
    )

    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "login1", "01", "5.0"],
        ["Student, Unregistered", "1002", "sis-1002", "login2", "01", "0.0"],
    ]
    assert "Template students without registered instances:" in out
    assert "Student, Unregistered" in out


def test_canvas_grades_matches_when_claims_name_has_middle_name(tmp_path, monkeypatch):
    """Match should succeed when Harvard claims include a full middle name."""
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    roster_entry = {
        A.USER_ID: "user-1",
        "email": "simson@example.edu",
        "preferred_name": "Sim Garfinkel",
        "claims": {"name": "Simson Lee Garfinkel"},
    }

    rows, out = _run_canvas_grades(tmp_path, monkeypatch, [roster_entry])

    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "login1", "01", "5.0"],
    ], "Expected match via middle-name stripping"
    assert "Template students without registered instances:" not in out
