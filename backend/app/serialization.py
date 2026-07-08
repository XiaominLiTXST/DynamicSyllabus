"""Convert ORM objects to/from the plain `state` dict used for the LLM context,
the diff, and ChangeLog snapshots. The state dict is fully JSON-serializable
(all dates are ISO strings)."""

from sqlmodel import Session, select

from .models import Assessment, ClassMeeting, Course


def reading_to_dict(r) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "citation": r.citation,
        "url": r.url,
        "required": r.required,
    }


def meeting_to_dict(m) -> dict:
    return {
        "id": m.id,
        "date": m.date.isoformat(),
        "position": m.position,
        "title": m.title,
        "status": m.status,
        "location": m.location,
        "notes": m.notes,
        "topics": list(m.topics or []),
        "readings": [
            reading_to_dict(r) for r in sorted(m.readings, key=lambda r: r.id or 0)
        ],
    }


def assessment_to_dict(a) -> dict:
    return {
        "id": a.id,
        "kind": a.kind,
        "title": a.title,
        "due_date": a.due_date.isoformat(),
        "linked_meeting_id": a.linked_meeting_id,
        "description": a.description,
        "status": a.status,
    }


def course_to_state(course, meetings, assessments) -> dict:
    return {
        "course": {
            "id": course.id,
            "title": course.title,
            "term": course.term,
            "instructor": course.instructor,
            "timezone": course.timezone,
            "meeting_days": list(course.meeting_days or []),
            "start_date": course.start_date.isoformat(),
            "end_date": course.end_date.isoformat(),
            "excluded_dates": list(course.excluded_dates or []),
            "public_token": course.public_token,
        },
        "meetings": [
            meeting_to_dict(m) for m in sorted(meetings, key=lambda m: m.position)
        ],
        "assessments": [
            assessment_to_dict(a)
            for a in sorted(assessments, key=lambda a: (a.due_date, a.id or 0))
        ],
    }


def load_state(session: Session, course_id: int) -> dict | None:
    course = session.get(Course, course_id)
    if course is None:
        return None
    meetings = session.exec(
        select(ClassMeeting).where(ClassMeeting.course_id == course_id)
    ).all()
    assessments = session.exec(
        select(Assessment).where(Assessment.course_id == course_id)
    ).all()
    return course_to_state(course, meetings, assessments)
