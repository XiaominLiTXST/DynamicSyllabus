"""The safe-edit core.

Operations are a typed Pydantic union (the same schema is handed to the LLM as a
tool). `apply_operations` is *pure*: it takes a JSON-serializable course `state`
dict and returns a new one, never touching the database. New entities created
during apply get temporary negative ids so the diff and the DB reconciler can
track them.
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from typing import Annotated, Literal, Optional, Union

from pydantic import BaseModel, Field

from . import scheduling


class OperationError(Exception):
    """Raised when an operation references something that doesn't exist or is
    otherwise impossible to apply. Surfaced to the user as a friendly message."""


# --- Operation schema (also the LLM tool schema) --------------------------------


class ShiftDates(BaseModel):
    op: Literal["shift_dates"]
    by_days: int = Field(description="Days to shift; positive = later, negative = earlier.")
    from_date: Optional[str] = Field(
        default=None,
        description="ISO date; only meetings/assessments on or after this move. Null = all.",
    )
    include_assessments: bool = Field(
        default=True, description="Also shift assignment/quiz/exam due dates."
    )


class ShiftTopics(BaseModel):
    op: Literal["shift_topics"]
    by_meetings: int = Field(
        default=1,
        description="How many class meetings to push topics/readings later. "
        "For 'one week' use the number of meetings per week.",
    )
    from_position: Optional[int] = Field(
        default=None, description="Only shift content at this meeting position or later."
    )


class MoveAssessmentDue(BaseModel):
    op: Literal["move_assessment_due"]
    assessment_id: int
    new_due_date: str = Field(description="ISO date.")


class AddAssessment(BaseModel):
    op: Literal["add_assessment"]
    kind: Literal["assignment", "quiz", "exam"]
    title: str
    due_date: Optional[str] = Field(default=None, description="ISO date.")
    after_meeting_id: Optional[int] = Field(
        default=None,
        description="Place it on the class meeting right after this meeting id "
        "(use when the user says 'after the X lecture'). Provide this OR due_date.",
    )
    description: Optional[str] = None


class CancelMeeting(BaseModel):
    op: Literal["cancel_meeting"]
    meeting_id: int
    reshuffle_content: bool = Field(
        default=True,
        description="Push this meeting's planned topics (and everything after) "
        "down to later meetings, extending the term if needed.",
    )


class UpdateMeeting(BaseModel):
    op: Literal["update_meeting"]
    meeting_id: int
    title: Optional[str] = None
    topics: Optional[list[str]] = None
    notes: Optional[str] = None
    status: Optional[Literal["scheduled", "canceled"]] = None


Operation = Annotated[
    Union[
        ShiftDates,
        ShiftTopics,
        MoveAssessmentDue,
        AddAssessment,
        CancelMeeting,
        UpdateMeeting,
    ],
    Field(discriminator="op"),
]


class OperationSet(BaseModel):
    explanation: str = Field(
        default="", description="One or two sentences describing the change for the instructor."
    )
    needs_clarification: Optional[str] = Field(
        default=None,
        description="If the instruction is ambiguous (e.g. shift dates vs. shift "
        "content), put your clarifying question here and leave operations empty.",
    )
    operations: list[Operation] = Field(default_factory=list)


# --- Apply ----------------------------------------------------------------------


def _d(s) -> date:
    return scheduling.to_date(s)


def _iso(d: date) -> str:
    return d.isoformat()


def _excluded(state) -> list:
    return [_d(x) for x in state["course"].get("excluded_dates", [])]


def _sorted_meetings(state) -> list:
    return sorted(state["meetings"], key=lambda m: m["position"])


def _new_meeting_id(state) -> int:
    ids = [m["id"] for m in state["meetings"] if isinstance(m["id"], int)]
    return min([0, *ids]) - 1


def _new_assessment_id(state) -> int:
    ids = [a["id"] for a in state["assessments"] if isinstance(a["id"], int)]
    return min([0, *ids]) - 1


def _empty_content() -> dict:
    return {"topics": [], "readings": [], "title": None}


def _content_of(m) -> dict:
    return {"topics": list(m["topics"]), "readings": list(m["readings"]), "title": m.get("title")}


def _set_content(m, content) -> None:
    m["topics"] = list(content["topics"])
    m["readings"] = list(content["readings"])
    m["title"] = content["title"]


def _renumber_and_fix_bounds(state) -> None:
    meetings = sorted(state["meetings"], key=lambda m: (_d(m["date"]), m["position"]))
    for i, m in enumerate(meetings):
        m["position"] = i
    state["meetings"] = meetings
    if meetings:
        state["course"]["start_date"] = min(m["date"] for m in meetings)
        state["course"]["end_date"] = max(m["date"] for m in meetings)


def _reflow(state, pivot: int, k: int, skip=()):
    """Shift content blocks down. Insert `k` empty slots at `pivot`; skipped slot
    indices (e.g. a canceled meeting) receive no content. Overflow content beyond
    the last meeting creates new dated meetings following the course pattern."""
    meetings = _sorted_meetings(state)
    skip = set(skip)
    contents = [_content_of(m) for m in meetings]
    queue = [_empty_content() for _ in range(k)] + contents[pivot:]

    for i in range(pivot, len(meetings)):
        if i in skip:
            _set_content(meetings[i], _empty_content())

    targets = [i for i in range(pivot, len(meetings)) if i not in skip]
    qi = 0
    for ti in targets:
        _set_content(meetings[ti], queue[qi] if qi < len(queue) else _empty_content())
        if qi < len(queue):
            qi += 1

    remaining = queue[qi:]
    if remaining:
        last = _d(meetings[-1]["date"])
        new_dates = scheduling.next_meeting_dates_after(
            last, state["course"]["meeting_days"], len(remaining), _excluded(state)
        )
        for idx, content in enumerate(remaining):
            d = new_dates[idx] if idx < len(new_dates) else last + timedelta(days=7 * (idx + 1))
            new_m = {
                "id": _new_meeting_id(state),
                "date": _iso(d),
                "position": len(state["meetings"]),
                "title": None,
                "status": "scheduled",
                "location": None,
                "notes": None,
                "topics": [],
                "readings": [],
            }
            _set_content(new_m, content)
            state["meetings"].append(new_m)

    _renumber_and_fix_bounds(state)


def _apply_shift_dates(state, op: ShiftDates):
    frm = _d(op.from_date) if op.from_date else None
    delta = timedelta(days=op.by_days)
    for m in state["meetings"]:
        if frm is None or _d(m["date"]) >= frm:
            m["date"] = _iso(_d(m["date"]) + delta)
    if op.include_assessments:
        for a in state["assessments"]:
            if frm is None or _d(a["due_date"]) >= frm:
                a["due_date"] = _iso(_d(a["due_date"]) + delta)
    _renumber_and_fix_bounds(state)


def _apply_shift_topics(state, op: ShiftTopics):
    meetings = _sorted_meetings(state)
    if not meetings or op.by_meetings <= 0:
        return
    if op.from_position is not None:
        pivot = next(
            (i for i, m in enumerate(meetings) if m["position"] >= op.from_position),
            len(meetings),
        )
    else:
        pivot = 0
    _reflow(state, pivot=pivot, k=op.by_meetings)


def _apply_move_assessment_due(state, op: MoveAssessmentDue):
    for a in state["assessments"]:
        if a["id"] == op.assessment_id:
            a["due_date"] = _iso(_d(op.new_due_date))
            return
    raise OperationError(f"No assessment with id {op.assessment_id}.")


def _apply_add_assessment(state, op: AddAssessment):
    due = op.due_date
    linked = None
    if due is None and op.after_meeting_id is not None:
        meetings = _sorted_meetings(state)
        idx = next(
            (i for i, m in enumerate(meetings) if m["id"] == op.after_meeting_id), None
        )
        if idx is None:
            raise OperationError(f"No meeting with id {op.after_meeting_id}.")
        target = meetings[idx + 1] if idx + 1 < len(meetings) else meetings[idx]
        due, linked = target["date"], target["id"]
    if due is None:
        raise OperationError("add_assessment needs a due_date or after_meeting_id.")
    state["assessments"].append(
        {
            "id": _new_assessment_id(state),
            "kind": op.kind,
            "title": op.title,
            "due_date": _iso(_d(due)),
            "linked_meeting_id": linked,
            "description": op.description,
            "status": "active",
        }
    )


def _apply_cancel_meeting(state, op: CancelMeeting):
    meetings = _sorted_meetings(state)
    idx = next((i for i, m in enumerate(meetings) if m["id"] == op.meeting_id), None)
    if idx is None:
        raise OperationError(f"No meeting with id {op.meeting_id}.")
    meetings[idx]["status"] = "canceled"
    if op.reshuffle_content:
        _reflow(state, pivot=idx, k=0, skip={idx})


def _apply_update_meeting(state, op: UpdateMeeting):
    for m in state["meetings"]:
        if m["id"] == op.meeting_id:
            if op.title is not None:
                m["title"] = op.title
            if op.topics is not None:
                m["topics"] = list(op.topics)
            if op.notes is not None:
                m["notes"] = op.notes
            if op.status is not None:
                m["status"] = op.status
            return
    raise OperationError(f"No meeting with id {op.meeting_id}.")


_DISPATCH = {
    ShiftDates: _apply_shift_dates,
    ShiftTopics: _apply_shift_topics,
    MoveAssessmentDue: _apply_move_assessment_due,
    AddAssessment: _apply_add_assessment,
    CancelMeeting: _apply_cancel_meeting,
    UpdateMeeting: _apply_update_meeting,
}


def apply_operations(state: dict, operations) -> dict:
    """Return a new state with all operations applied. Pure — input is not mutated."""
    new_state = copy.deepcopy(state)
    for op in operations:
        handler = _DISPATCH.get(type(op))
        if handler is None:
            raise OperationError(f"Unknown operation: {getattr(op, 'op', op)}")
        handler(new_state, op)
    return new_state


# --- Diff -----------------------------------------------------------------------


def _readings_sig(m) -> list:
    return [(r["title"], r.get("citation"), r.get("url")) for r in m["readings"]]


def compute_diff(before: dict, after: dict) -> list[dict]:
    """Human-readable change list for the preview UI."""
    changes: list[dict] = []

    bm = {m["id"]: m for m in before["meetings"]}
    am = {m["id"]: m for m in after["meetings"]}
    for mid, m in am.items():
        label = m.get("title") or (m["topics"][0] if m["topics"] else "class")
        if mid not in bm:
            changes.append({"type": "meeting_added", "summary": f"New class on {m['date']}: {label}"})
            continue
        b = bm[mid]
        if b["date"] != m["date"]:
            changes.append({"type": "meeting_moved", "summary": f"{label}: {b['date']} → {m['date']}"})
        if b["status"] != m["status"]:
            changes.append({"type": "meeting_status", "summary": f"Class on {m['date']} → {m['status']}"})
        if b["topics"] != m["topics"] or _readings_sig(b) != _readings_sig(m) or b.get("title") != m.get("title"):
            changes.append({"type": "meeting_content", "summary": f"Topics/readings updated for {m['date']}"})
    for mid, b in bm.items():
        if mid not in am:
            changes.append({"type": "meeting_removed", "summary": f"Removed class on {b['date']}"})

    ba = {a["id"]: a for a in before["assessments"]}
    aa = {a["id"]: a for a in after["assessments"]}
    for aid, a in aa.items():
        if aid not in ba:
            changes.append({"type": "assessment_added", "summary": f"Added {a['kind']} '{a['title']}' due {a['due_date']}"})
            continue
        b = ba[aid]
        if b["due_date"] != a["due_date"]:
            changes.append({"type": "assessment_moved", "summary": f"{a['title']} due {b['due_date']} → {a['due_date']}"})
        if b["status"] != a["status"]:
            changes.append({"type": "assessment_status", "summary": f"{a['title']} → {a['status']}"})
        if b["title"] != a["title"] or b["kind"] != a["kind"]:
            changes.append({"type": "assessment_updated", "summary": f"Updated {a['title']}"})
    for aid, b in ba.items():
        if aid not in aa:
            changes.append({"type": "assessment_removed", "summary": f"Removed {b['title']}"})

    return changes
