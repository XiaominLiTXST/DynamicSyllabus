from datetime import date

from app import scheduling


def test_generate_meeting_dates_mon_wed():
    # Sep 7 2026 is a Monday.
    dates = scheduling.generate_meeting_dates(
        date(2026, 9, 7), date(2026, 9, 20), ["Mon", "Wed"]
    )
    assert dates == [
        date(2026, 9, 7),
        date(2026, 9, 9),
        date(2026, 9, 14),
        date(2026, 9, 16),
    ]


def test_generate_excludes_holidays():
    dates = scheduling.generate_meeting_dates(
        date(2026, 9, 7), date(2026, 9, 20), ["Mon", "Wed"], excluded=["2026-09-14"]
    )
    assert date(2026, 9, 14) not in dates
    assert len(dates) == 3


def test_next_meeting_dates_follow_pattern():
    nxt = scheduling.next_meeting_dates_after(date(2026, 9, 16), ["Mon", "Wed"], 2)
    assert nxt == [date(2026, 9, 21), date(2026, 9, 23)]


def test_empty_when_no_meeting_days():
    assert scheduling.generate_meeting_dates(date(2026, 9, 7), date(2026, 9, 20), []) == []
