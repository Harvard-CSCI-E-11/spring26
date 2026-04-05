from e11.e11_common import A, select_highest_grade_records


def test_select_highest_grade_records_prefers_later_record_on_tie():
    items = [
        {
            A.USER_ID: "user-1",
            A.SK: "grade#lab1#2026-02-01T10:00:00.000000",
            A.SCORE: "5.0",
        },
        {
            A.USER_ID: "user-1",
            A.SK: "grade#lab1#2026-02-02T10:00:00.000000",
            A.SCORE: "5.0",
        },
    ]

    highest = select_highest_grade_records(items)

    assert len(highest) == 1
    assert highest[0][A.SK] == "grade#lab1#2026-02-02T10:00:00.000000"


def _grade_item(timestamp, score):
    return {
        A.USER_ID: "user-1",
        A.SK: f"grade#lab1#{timestamp}",
        A.SCORE: score,
    }


def test_select_highest_grade_records_picks_5_first():
    items = [
        _grade_item("2026-02-03T10:00:00.000000", "5.0"),
        _grade_item("2026-02-01T10:00:00.000000", "2.5"),
        _grade_item("2026-02-02T10:00:00.000000", "4.0"),
    ]

    highest = select_highest_grade_records(items)

    assert len(highest) == 1
    assert highest[0][A.SCORE] == "5.0"


def test_select_highest_grade_records_picks_5_middle():
    items = [
        _grade_item("2026-02-01T10:00:00.000000", "2.5"),
        _grade_item("2026-02-03T10:00:00.000000", "5.0"),
        _grade_item("2026-02-02T10:00:00.000000", "4.0"),
    ]

    highest = select_highest_grade_records(items)

    assert len(highest) == 1
    assert highest[0][A.SCORE] == "5.0"


def test_select_highest_grade_records_picks_5_last():
    items = [
        _grade_item("2026-02-01T10:00:00.000000", "2.5"),
        _grade_item("2026-02-02T10:00:00.000000", "4.0"),
        _grade_item("2026-02-03T10:00:00.000000", "5.0"),
    ]

    highest = select_highest_grade_records(items)

    assert len(highest) == 1
    assert highest[0][A.SCORE] == "5.0"
