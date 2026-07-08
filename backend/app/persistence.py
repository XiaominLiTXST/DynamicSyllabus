"""Reconcile the database to match a target `state` dict (used for both applying
a change set and restoring a snapshot during undo). Entities are matched by
positive id; entities in the state with non-positive/temp ids are created; DB
rows absent from the target state are deleted."""

from sqlmodel import Session, select

from .models import Assessment, ClassMeeting, Course, Reading, utcnow
from .scheduling import to_date


def _is_existing(entity_id) -> bool:
    return isinstance(entity_id, int) and entity_id > 0


def _reconcile_readings(session: Session, meeting: ClassMeeting, readings_state) -> None:
    existing = {
        r.id: r
        for r in session.exec(
            select(Reading).where(Reading.meeting_id == meeting.id)
        ).all()
    }
    keep: set[int] = set()
    for rs in readings_state:
        rid = rs.get("id")
        if _is_existing(rid) and rid in existing:
            r = existing[rid]
        else:
            r = Reading(meeting_id=meeting.id, title=rs["title"])
        r.meeting_id = meeting.id
        r.title = rs["title"]
        r.citation = rs.get("citation")
        r.url = rs.get("url")
        r.required = rs.get("required", True)
        session.add(r)
        session.flush()
        keep.add(r.id)
    for rid, r in existing.items():
        if rid not in keep:
            session.delete(r)


def reconcile(session: Session, course: Course, state: dict) -> None:
    c = state["course"]
    course.title = c["title"]
    course.term = c["term"]
    course.instructor = c["instructor"]
    course.timezone = c["timezone"]
    course.meeting_days = c["meeting_days"]
    course.start_date = to_date(c["start_date"])
    course.end_date = to_date(c["end_date"])
    course.excluded_dates = c["excluded_dates"]
    course.updated_at = utcnow()
    session.add(course)

    existing_m = {
        m.id: m
        for m in session.exec(
            select(ClassMeeting).where(ClassMeeting.course_id == course.id)
        ).all()
    }
    keep_m: set[int] = set()
    id_map: dict = {}  # temp meeting id -> real id, for assessment links
    for ms in sorted(state["meetings"], key=lambda x: x["position"]):
        mid = ms["id"]
        m = existing_m[mid] if (_is_existing(mid) and mid in existing_m) else ClassMeeting(course_id=course.id)
        m.course_id = course.id
        m.date = to_date(ms["date"])
        m.position = ms["position"]
        m.title = ms.get("title")
        m.status = ms["status"]
        m.location = ms.get("location")
        m.notes = ms.get("notes")
        m.topics = ms["topics"]
        session.add(m)
        session.flush()
        keep_m.add(m.id)
        id_map[mid] = m.id
        _reconcile_readings(session, m, ms["readings"])
    for mid, m in existing_m.items():
        if mid not in keep_m:
            session.delete(m)

    existing_a = {
        a.id: a
        for a in session.exec(
            select(Assessment).where(Assessment.course_id == course.id)
        ).all()
    }
    keep_a: set[int] = set()
    for as_ in state["assessments"]:
        aid = as_["id"]
        a = existing_a[aid] if (_is_existing(aid) and aid in existing_a) else Assessment(
            course_id=course.id, kind=as_["kind"], title=as_["title"], due_date=to_date(as_["due_date"])
        )
        a.course_id = course.id
        a.kind = as_["kind"]
        a.title = as_["title"]
        a.due_date = to_date(as_["due_date"])
        a.description = as_.get("description")
        a.status = as_["status"]
        linked = as_.get("linked_meeting_id")
        if linked in id_map:  # remap temp -> real
            linked = id_map[linked]
        a.linked_meeting_id = linked if _is_existing(linked) else None
        session.add(a)
        session.flush()
        keep_a.add(a.id)
    for aid, a in existing_a.items():
        if aid not in keep_a:
            session.delete(a)
