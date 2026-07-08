"""Request bodies for the API. Responses are mostly the `state` dict from
serialization.py."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    password: str


class CourseCreate(BaseModel):
    title: str
    term: str = ""
    instructor: str = ""
    timezone: str = "America/New_York"
    meeting_days: list[str] = Field(default_factory=list)
    start_date: date
    end_date: date
    excluded_dates: list[date] = Field(default_factory=list)


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    term: Optional[str] = None
    instructor: Optional[str] = None
    timezone: Optional[str] = None
    meeting_days: Optional[list[str]] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    excluded_dates: Optional[list[date]] = None


class CourseClone(BaseModel):
    source_course_id: int
    title: str
    term: str = ""
    instructor: str = ""
    timezone: str = "America/New_York"
    meeting_days: list[str] = Field(default_factory=list)
    start_date: date
    end_date: date
    excluded_dates: list[date] = Field(default_factory=list)


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    topics: Optional[list[str]] = None
    notes: Optional[str] = None
    location: Optional[str] = None
    status: Optional[str] = None


class ReadingCreate(BaseModel):
    title: str
    citation: Optional[str] = None
    url: Optional[str] = None
    required: bool = True


class AssessmentCreate(BaseModel):
    kind: str  # assignment | quiz | exam
    title: str
    due_date: date
    linked_meeting_id: Optional[int] = None
    description: Optional[str] = None


class AssessmentUpdate(BaseModel):
    kind: Optional[str] = None
    title: Optional[str] = None
    due_date: Optional[date] = None
    description: Optional[str] = None
    status: Optional[str] = None


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatMessage] = Field(default_factory=list)


class ApplyRequest(BaseModel):
    operations: list[dict]
    user_message: Optional[str] = None
