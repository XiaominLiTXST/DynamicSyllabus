"""Date math: generate the dated meeting grid from a weekly meeting pattern."""

from datetime import date, datetime, timedelta

from dateutil.rrule import FR, MO, SA, SU, TH, TU, WE, WEEKLY, rrule

WEEKDAY_RRULE = {"Mon": MO, "Tue": TU, "Wed": WE, "Thu": TH, "Fri": FR, "Sat": SA, "Sun": SU}
WEEKDAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def to_date(value) -> date:
    if isinstance(value, date):
        return value
    return date.fromisoformat(value)


def iso(value: date) -> str:
    return to_date(value).isoformat()


def _byweekday(meeting_days):
    return [WEEKDAY_RRULE[d] for d in meeting_days if d in WEEKDAY_RRULE]


def generate_meeting_dates(
    start: date, end: date, meeting_days, excluded=()
) -> list[date]:
    """All dates between start and end (inclusive) that fall on a meeting day,
    minus any excluded dates."""
    byweekday = _byweekday(meeting_days)
    if not byweekday or start > end:
        return []
    excluded_set = {to_date(d) for d in excluded}
    out = []
    for dt in rrule(
        WEEKLY,
        dtstart=datetime(start.year, start.month, start.day),
        until=datetime(end.year, end.month, end.day),
        byweekday=byweekday,
    ):
        d = dt.date()
        if d not in excluded_set:
            out.append(d)
    return out


def next_meeting_dates_after(
    last_date: date, meeting_days, count: int, excluded=()
) -> list[date]:
    """The next `count` meeting dates strictly after last_date, following the pattern."""
    if count <= 0:
        return []
    byweekday = _byweekday(meeting_days)
    excluded_set = {to_date(d) for d in excluded}
    out: list[date] = []
    if not byweekday:
        # Fallback: weekly cadence so content never silently disappears.
        d = last_date
        while len(out) < count:
            d = d + timedelta(days=7)
            out.append(d)
        return out
    start = last_date + timedelta(days=1)
    for dt in rrule(
        WEEKLY, dtstart=datetime(start.year, start.month, start.day), byweekday=byweekday
    ):
        d = dt.date()
        if d <= last_date or d in excluded_set:
            continue
        out.append(d)
        if len(out) >= count:
            break
    return out
