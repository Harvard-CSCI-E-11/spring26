import argparse
import csv
from pathlib import Path


def test_canvas_grades_matches_middle_initial_and_preferred_name(tmp_path, monkeypatch, capsys):
    from e11.e11admin import staff
    from e11.e11_common import A

    staff.get_class_list.cache_clear()
    staff.userid_to_user.cache_clear()

    template = tmp_path / "template.csv"
    outfile = tmp_path / "out.csv"
    with template.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Student",
            "ID",
            "SIS User ID",
            "SIS Login ID",
            "Section",
            "Lab 1",
        ])
        writer.writerow(["Points Possible", "", "", "", "", "5"])
        writer.writerow([
            "Garfinkel, Simson",
            "1001",
            "sis-1001",
            "sgarfinkel",
            "01",
            "",
        ])

    monkeypatch.setattr(
        staff,
        "get_class_list",
        lambda: [
            {
                A.USER_ID: "user-1",
                "email": "simson@example.edu",
                "preferred_name": "Simson Garfinkel",
                "claims": {"name": "Simson L. Garfinkel"},
            }
        ],
    )
    monkeypatch.setattr(
        staff,
        "get_items",
        lambda lab: [
            {
                A.USER_ID: "user-1",
                A.SK: "grade#lab1#2026-04-06T12:00:00.000000",
                A.SCORE: "5.0",
            }
        ],
    )
    monkeypatch.setattr(staff, "get_highest_grades", lambda items: items)

    staff.canvas_grades(argparse.Namespace(lab="lab1", template=template, outfile=outfile))

    rows = list(csv.reader(outfile.open(encoding="utf-8", newline="")))
    assert rows == [
        ["Student", "ID", "SIS User ID", "SIS Login ID", "Section", "Lab 1"],
        ["Garfinkel, Simson", "1001", "sis-1001", "sgarfinkel", "01", "5.0"],
    ]

    out = capsys.readouterr().out
    assert "Unmatched.  Will not continued" not in out
