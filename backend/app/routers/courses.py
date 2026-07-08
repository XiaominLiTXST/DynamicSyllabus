import hmac
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..auth import create_token, require_admin
from ..config import settings
from ..db import get_session
from ..models import Assessment, ChangeLog, ClassMeeting, Course, Reading, utcnow
from ..scheduling import generate_meeting_dates
from ..schemas import (
    AssessmentCreate,
    AssessmentUpdate,
    CourseClone,
    CourseCreate,
    CourseUpdate,
    LoginRequest,
    MeetingUpdate,
    ReadingCreate,
)
from ..serialization import assessment_to_dict, load_state, meeting_to_dict

router = APIRouter(prefix="/api", tags=["courses"])


@router.post("/login")
def login(body: LoginRequest):
    if not hmac.compare_digest(body.password, settings.admin_password):
        raise HTTPException(status_code=401, detail="Invalid password")
    return {"token": create_token()}


def _get_course(session: Session, course_id: int) -> Course:
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


def _date_list(dates) -> list[str]:
    return [d.isoformat() for d in dates]


def _course_schedule_values(course: Course, data: dict) -> tuple:
    return (
        data.get("start_date", course.start_date),
        data.get("end_date", course.end_date),
        data.get("meeting_days", course.meeting_days),
        data.get("excluded_dates", course.excluded_dates),
    )


def _delete_meeting_readings(session: Session, meeting_id: int) -> None:
    readings = session.exec(
        select(Reading).where(Reading.meeting_id == meeting_id)
    ).all()
    for reading in readings:
        session.delete(reading)


def _regenerate_meetings(
    session: Session,
    course: Course,
    start_date,
    end_date,
    meeting_days,
    excluded_dates,
) -> None:
    """Rebuild the meeting date grid while preserving content by position."""
    existing = sorted(
        session.exec(
            select(ClassMeeting).where(ClassMeeting.course_id == course.id)
        ).all(),
        key=lambda m: m.position,
    )
    new_dates = generate_meeting_dates(start_date, end_date, meeting_days, excluded_dates)
    keep_ids: set[int] = set()
    linked_updates: dict[int, ClassMeeting] = {}

    for position, meeting_date in enumerate(new_dates):
        if position < len(existing):
            meeting = existing[position]
        else:
            meeting = ClassMeeting(course_id=course.id, topics=[])
        old_id = meeting.id
        meeting.course_id = course.id
        meeting.date = meeting_date
        meeting.position = position
        session.add(meeting)
        session.flush()
        keep_ids.add(meeting.id)
        if old_id:
            linked_updates[old_id] = meeting

    for meeting in existing:
        if meeting.id not in keep_ids:
            _delete_meeting_readings(session, meeting.id)
            session.delete(meeting)

    assessments = session.exec(
        select(Assessment).where(Assessment.course_id == course.id)
    ).all()
    for assessment in assessments:
        linked = assessment.linked_meeting_id
        if linked in linked_updates:
            assessment.linked_meeting_id = linked_updates[linked].id
            assessment.due_date = linked_updates[linked].date
            session.add(assessment)
        elif linked:
            assessment.linked_meeting_id = None
            session.add(assessment)


def _copy_assessment_due(source: Assessment, source_course: Course, new_course: Course, meeting_map: dict[int, ClassMeeting]):
    if source.linked_meeting_id in meeting_map:
        return meeting_map[source.linked_meeting_id].date
    return source.due_date + (new_course.start_date - source_course.start_date)


@router.post("/courses", dependencies=[Depends(require_admin)])
def create_course(body: CourseCreate, session: Session = Depends(get_session)):
    course = Course(
        title=body.title,
        term=body.term,
        instructor=body.instructor,
        timezone=body.timezone,
        meeting_days=body.meeting_days,
        start_date=body.start_date,
        end_date=body.end_date,
        excluded_dates=[d.isoformat() for d in body.excluded_dates],
        public_token=secrets.token_urlsafe(9),
    )
    session.add(course)
    session.commit()
    session.refresh(course)

    dates = generate_meeting_dates(
        body.start_date, body.end_date, body.meeting_days, body.excluded_dates
    )
    for i, d in enumerate(dates):
        session.add(ClassMeeting(course_id=course.id, date=d, position=i, topics=[]))
    session.commit()
    return load_state(session, course.id)


@router.post("/courses/clone", dependencies=[Depends(require_admin)])
def clone_course(body: CourseClone, session: Session = Depends(get_session)):
    source = _get_course(session, body.source_course_id)
    source_meetings = sorted(
        session.exec(
            select(ClassMeeting).where(ClassMeeting.course_id == source.id)
        ).all(),
        key=lambda m: m.position,
    )
    source_assessments = session.exec(
        select(Assessment).where(Assessment.course_id == source.id)
    ).all()

    course = Course(
        title=body.title,
        term=body.term,
        instructor=body.instructor,
        timezone=body.timezone,
        meeting_days=body.meeting_days,
        start_date=body.start_date,
        end_date=body.end_date,
        excluded_dates=_date_list(body.excluded_dates),
        public_token=secrets.token_urlsafe(9),
    )
    session.add(course)
    session.flush()

    new_dates = generate_meeting_dates(
        body.start_date, body.end_date, body.meeting_days, body.excluded_dates
    )
    meeting_map: dict[int, ClassMeeting] = {}
    for position, meeting_date in enumerate(new_dates):
        source_meeting = source_meetings[position] if position < len(source_meetings) else None
        meeting = ClassMeeting(
            course_id=course.id,
            date=meeting_date,
            position=position,
            title=source_meeting.title if source_meeting else None,
            status=source_meeting.status if source_meeting else "scheduled",
            location=source_meeting.location if source_meeting else None,
            notes=source_meeting.notes if source_meeting else None,
            topics=list(source_meeting.topics or []) if source_meeting else [],
        )
        session.add(meeting)
        session.flush()
        if source_meeting:
            meeting_map[source_meeting.id] = meeting
            for reading in sorted(source_meeting.readings, key=lambda r: r.id or 0):
                session.add(
                    Reading(
                        meeting_id=meeting.id,
                        title=reading.title,
                        citation=reading.citation,
                        url=reading.url,
                        required=reading.required,
                    )
                )

    for source_assessment in source_assessments:
        session.add(
            Assessment(
                course_id=course.id,
                kind=source_assessment.kind,
                title=source_assessment.title,
                due_date=_copy_assessment_due(
                    source_assessment, source, course, meeting_map
                ),
                linked_meeting_id=(
                    meeting_map[source_assessment.linked_meeting_id].id
                    if source_assessment.linked_meeting_id in meeting_map
                    else None
                ),
                description=source_assessment.description,
                status=source_assessment.status,
            )
        )

    session.commit()
    return load_state(session, course.id)


@router.get("/courses", dependencies=[Depends(require_admin)])
def list_courses(session: Session = Depends(get_session)):
    courses = session.exec(select(Course)).all()
    return [
        {
            "id": c.id,
            "title": c.title,
            "term": c.term,
            "public_token": c.public_token,
            "updated_at": c.updated_at.isoformat(),
        }
        for c in courses
    ]


@router.get("/courses/{course_id}", dependencies=[Depends(require_admin)])
def get_course(course_id: int, session: Session = Depends(get_session)):
    state = load_state(session, course_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Course not found")
    return state


@router.patch("/courses/{course_id}", dependencies=[Depends(require_admin)])
def update_course(
    course_id: int, body: CourseUpdate, session: Session = Depends(get_session)
):
    course = _get_course(session, course_id)
    data = body.model_dump(exclude_unset=True)
    if "excluded_dates" in data:
        data["excluded_dates"] = _date_list(data["excluded_dates"])

    schedule_fields = {"start_date", "end_date", "meeting_days", "excluded_dates"}
    schedule_changed = any(field in data for field in schedule_fields)
    start_date, end_date, meeting_days, excluded_dates = _course_schedule_values(
        course, data
    )
    if start_date > end_date:
        raise HTTPException(status_code=422, detail="Start date must be before end date")

    for field in ("title", "term", "instructor", "timezone"):
        if field in data:
            setattr(course, field, data[field])
    if schedule_changed:
        course.start_date = start_date
        course.end_date = end_date
        course.meeting_days = meeting_days
        course.excluded_dates = excluded_dates
        _regenerate_meetings(
            session, course, start_date, end_date, meeting_days, excluded_dates
        )

    course.updated_at = utcnow()
    session.add(course)
    session.commit()
    return load_state(session, course.id)


@router.delete("/courses/{course_id}", dependencies=[Depends(require_admin)])
def delete_course(course_id: int, session: Session = Depends(get_session)):
    course = _get_course(session, course_id)
    meetings = session.exec(
        select(ClassMeeting).where(ClassMeeting.course_id == course_id)
    ).all()
    for meeting in meetings:
        _delete_meeting_readings(session, meeting.id)
        session.delete(meeting)
    for assessment in session.exec(
        select(Assessment).where(Assessment.course_id == course_id)
    ).all():
        session.delete(assessment)
    for log in session.exec(
        select(ChangeLog).where(ChangeLog.course_id == course_id)
    ).all():
        session.delete(log)
    session.delete(course)
    session.commit()
    return {"ok": True}


@router.patch(
    "/courses/{course_id}/meetings/{meeting_id}",
    dependencies=[Depends(require_admin)],
)
def update_meeting(
    course_id: int,
    meeting_id: int,
    body: MeetingUpdate,
    session: Session = Depends(get_session),
):
    meeting = session.get(ClassMeeting, meeting_id)
    if meeting is None or meeting.course_id != course_id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    data = body.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(meeting, field, value)
    session.add(meeting)
    _touch(session, course_id)
    session.commit()
    session.refresh(meeting)
    return meeting_to_dict(meeting)


@router.post(
    "/courses/{course_id}/meetings/{meeting_id}/readings",
    dependencies=[Depends(require_admin)],
)
def add_reading(
    course_id: int,
    meeting_id: int,
    body: ReadingCreate,
    session: Session = Depends(get_session),
):
    meeting = session.get(ClassMeeting, meeting_id)
    if meeting is None or meeting.course_id != course_id:
        raise HTTPException(status_code=404, detail="Meeting not found")
    reading = Reading(meeting_id=meeting_id, **body.model_dump())
    session.add(reading)
    _touch(session, course_id)
    session.commit()
    session.refresh(meeting)
    return meeting_to_dict(meeting)


@router.delete(
    "/courses/{course_id}/readings/{reading_id}",
    dependencies=[Depends(require_admin)],
)
def delete_reading(
    course_id: int, reading_id: int, session: Session = Depends(get_session)
):
    reading = session.get(Reading, reading_id)
    if reading is None:
        raise HTTPException(status_code=404, detail="Reading not found")
    session.delete(reading)
    _touch(session, course_id)
    session.commit()
    return {"ok": True}


@router.post("/courses/{course_id}/assessments", dependencies=[Depends(require_admin)])
def add_assessment(
    course_id: int, body: AssessmentCreate, session: Session = Depends(get_session)
):
    _get_course(session, course_id)
    assessment = Assessment(course_id=course_id, **body.model_dump())
    session.add(assessment)
    _touch(session, course_id)
    session.commit()
    session.refresh(assessment)
    return assessment_to_dict(assessment)


@router.patch(
    "/courses/{course_id}/assessments/{assessment_id}",
    dependencies=[Depends(require_admin)],
)
def update_assessment(
    course_id: int,
    assessment_id: int,
    body: AssessmentUpdate,
    session: Session = Depends(get_session),
):
    assessment = session.get(Assessment, assessment_id)
    if assessment is None or assessment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(assessment, field, value)
    session.add(assessment)
    _touch(session, course_id)
    session.commit()
    session.refresh(assessment)
    return assessment_to_dict(assessment)


@router.delete(
    "/courses/{course_id}/assessments/{assessment_id}",
    dependencies=[Depends(require_admin)],
)
def delete_assessment(
    course_id: int, assessment_id: int, session: Session = Depends(get_session)
):
    assessment = session.get(Assessment, assessment_id)
    if assessment is None or assessment.course_id != course_id:
        raise HTTPException(status_code=404, detail="Assessment not found")
    session.delete(assessment)
    _touch(session, course_id)
    session.commit()
    return {"ok": True}


def _touch(session: Session, course_id: int) -> None:
    course = session.get(Course, course_id)
    if course:
        course.updated_at = utcnow()
        session.add(course)
