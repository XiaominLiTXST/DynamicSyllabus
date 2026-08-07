import re
import unicodedata

from sqlmodel import Session, select

from .models import Course


def course_slug(title: str, term: str) -> str:
    """Build a URL-safe course/term slug such as cs1428fall2026."""
    source = unicodedata.normalize("NFKD", f"{title}{term}")
    ascii_source = source.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "", ascii_source.lower())
    if not slug:
        slug = "course"
    if slug in {"api", "s"}:
        slug = f"course{slug}"
    return slug


def available_course_slug(
    session: Session,
    title: str,
    term: str,
    *,
    exclude_course_id: int | None = None,
) -> str:
    base = course_slug(title, term)
    courses = session.exec(select(Course)).all()
    used = {
        course.public_token
        for course in courses
        if course.id != exclude_course_id
    }
    if base not in used:
        return base
    suffix = 2
    while f"{base}-{suffix}" in used:
        suffix += 1
    return f"{base}-{suffix}"


def migrate_public_slugs(session: Session) -> None:
    """Replace legacy random tokens while preserving already valid slugs."""
    courses = sorted(session.exec(select(Course)).all(), key=lambda c: c.id or 0)
    used: set[str] = set()
    pending: list[Course] = []

    for course in courses:
        base = course_slug(course.title, course.term)
        is_course_slug = course.public_token == base or bool(
            re.fullmatch(rf"{re.escape(base)}-[2-9][0-9]*", course.public_token)
        )
        if is_course_slug and course.public_token not in used:
            used.add(course.public_token)
        else:
            pending.append(course)

    for course in pending:
        base = course_slug(course.title, course.term)
        slug = base
        suffix = 2
        while slug in used:
            slug = f"{base}-{suffix}"
            suffix += 1
        course.public_token = slug
        used.add(slug)
        session.add(course)

    if pending:
        session.commit()
