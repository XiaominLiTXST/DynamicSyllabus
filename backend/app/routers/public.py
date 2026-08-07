from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..db import get_session
from ..models import Course
from ..serialization import load_state

router = APIRouter(prefix="/api/public", tags=["public"])


@router.get("/{slug}")
def public_syllabus(slug: str, session: Session = Depends(get_session)):
    """Read-only syllabus for students — no auth, just the unguessable token."""
    course = session.exec(select(Course).where(Course.public_token == slug)).first()
    if course is None:
        raise HTTPException(status_code=404, detail="Syllabus not found")

    state = load_state(session, course.id)
    today = date.today().isoformat()

    upcoming_deadlines = sorted(
        [
            a
            for a in state["assessments"]
            if a["status"] == "active" and a["due_date"] >= today
        ],
        key=lambda a: a["due_date"],
    )[:5]
    latest_announcements = sorted(
        [
            a
            for a in state["announcements"]
            if a["status"] == "active" and a["publish_date"] <= today
        ],
        key=lambda a: (a["publish_date"], a["created_at"]),
        reverse=True,
    )[:3]
    next_class = next(
        (
            m
            for m in state["meetings"]
            if m["status"] != "canceled" and m["date"] >= today
        ),
        None,
    )

    course_public = dict(state["course"])
    course_public.pop("public_token", None)
    return {
        "course": course_public,
        "meetings": state["meetings"],
        "assessments": state["assessments"],
        "announcements": state["announcements"],
        "upcoming_deadlines": upcoming_deadlines,
        "latest_announcements": latest_announcements,
        "next_class": next_class,
        "updated_at": course.updated_at.isoformat(),
    }
