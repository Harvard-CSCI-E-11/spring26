import argparse
import csv
from pathlib import Path


def _make_template(tmp_path, template_name="Garfinkel, Simson"):
    """Create a Canvas template CSV with a single student row."""
    template = tmp_path / "template.csv"
    with template.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"])
        writer.writerow(["Points Possible", "", "", "", "", "5"])
        writer.writerow([template_name, "1001", "sis-1001", "sgarfinkel", "01", ""])
    return template


def _run_canvas_grades(tmp_path, monkeypatch, roster_entry):
    """Patch staff helpers and run canvas_grades; return (output_rows, stdout)."""
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    outfile = tmp_path / "out.csv"
    template = _make_template(tmp_path)

    monkeypatch.setattr(staff, "get_class_list", lambda: [roster_entry])
    monkeypatch.setattr(
        staff,
        "get_items",
        lambda lab: [
            {
                A.USER_ID: roster_entry[A.USER_ID],
                A.SK: "grade#lab1#2026-04-06T12:00:00.000000",
                A.SCORE: "5.0",
            }
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

    rows, out = _run_canvas_grades(tmp_path, monkeypatch, roster_entry)

    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "sgarfinkel", "01", "5.0"],
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

    rows, out = _run_canvas_grades(tmp_path, monkeypatch, roster_entry)

    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "sgarfinkel", "01", "5.0"],
    ], "Expected match via preferred_name"
    assert "Unmatched.  Will not continue" not in out
