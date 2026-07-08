from datetime import date, datetime, timezone

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Course(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    title: str
    term: str = ""
    instructor: str = ""
    timezone: str = "America/New_York"
    # Weekday abbreviations: Mon, Tue, Wed, Thu, Fri, Sat, Sun
    meeting_days: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    start_date: date
    end_date: date
    # ISO date strings (JSON can't hold date objects directly).
    excluded_dates: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    public_token: str = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    meetings: list["ClassMeeting"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    assessments: list["Assessment"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    announcements: list["Announcement"] = Relationship(
        back_populates="course",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class ClassMeeting(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    date: date
    position: int
    title: str | None = None
    status: str = "scheduled"  # "scheduled" | "canceled"
    location: str | None = None
    notes: str | None = None
    topics: list[str] = Field(default_factory=list, sa_column=Column(JSON))

    course: Course | None = Relationship(back_populates="meetings")
    readings: list["Reading"] = Relationship(
        back_populates="meeting",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )


class Reading(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    meeting_id: int = Field(foreign_key="classmeeting.id", index=True)
    title: str
    citation: str | None = None
    url: str | None = None
    required: bool = True

    meeting: ClassMeeting | None = Relationship(back_populates="readings")


class Assessment(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    kind: str  # "assignment" | "quiz" | "exam"
    title: str
    due_date: date
    linked_meeting_id: int | None = None
    description: str | None = None
    status: str = "active"  # "active" | "canceled"

    course: Course | None = Relationship(back_populates="assessments")


class Announcement(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    title: str
    body: str
    publish_date: date = Field(default_factory=date.today)
    status: str = "active"  # "active" | "archived"
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)

    course: Course | None = Relationship(back_populates="announcements")


class ChangeLog(SQLModel, table=True):
    """One row per applied change set — powers undo and 'updated' indicators."""

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(foreign_key="course.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    user_message: str | None = None
    summary: str | None = None
    operations: list = Field(default_factory=list, sa_column=Column(JSON))
    snapshot_before: dict = Field(default_factory=dict, sa_column=Column(JSON))
    undone: bool = False
