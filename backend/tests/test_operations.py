import copy

import pytest

from app import operations as ops
from app.operations import (
    AddAssessment,
    CancelMeeting,
    MoveAssessmentDue,
    OperationError,
    OperationSet,
    ShiftDates,
    ShiftTopics,
    apply_operations,
    compute_diff,
)


def sample_state():
    return {
        "course": {
            "id": 1, "title": "CS 250", "term": "F26", "instructor": "X",
            "timezone": "UTC", "meeting_days": ["Mon", "Wed"],
            "start_date": "2026-09-07", "end_date": "2026-09-16",
            "excluded_dates": [], "public_token": "t",
        },
        "meetings": [
            {"id": 1, "date": "2026-09-07", "position": 0, "title": "Intro", "status": "scheduled",
             "location": None, "notes": None, "topics": ["intro"],
             "readings": [{"id": 1, "title": "Ch1", "citation": None, "url": None, "required": True}]},
            {"id": 2, "date": "2026-09-09", "position": 1, "title": "Recursion", "status": "scheduled",
             "location": None, "notes": None, "topics": ["recursion"], "readings": []},
            {"id": 3, "date": "2026-09-14", "position": 2, "title": "Sorting", "status": "scheduled",
             "location": None, "notes": None, "topics": ["sorting"], "readings": []},
            {"id": 4, "date": "2026-09-16", "position": 3, "title": "Trees", "status": "scheduled",
             "location": None, "notes": None, "topics": ["trees"], "readings": []},
        ],
        "assessments": [
            {"id": 1, "kind": "assignment", "title": "Assignment 1", "due_date": "2026-09-11",
             "linked_meeting_id": None, "description": None, "status": "active"},
            {"id": 2, "kind": "assignment", "title": "Assignment 2", "due_date": "2026-09-18",
             "linked_meeting_id": None, "description": None, "status": "active"},
        ],
    }


def test_apply_is_pure():
    state = sample_state()
    frozen = copy.deepcopy(state)
    apply_operations(state, [ShiftDates(op="shift_dates", by_days=7)])
    assert state == frozen  # input untouched


def test_shift_dates_moves_meetings_and_assessments():
    after = apply_operations(sample_state(), [ShiftDates(op="shift_dates", by_days=7)])
    assert after["meetings"][0]["date"] == "2026-09-14"
    assert after["assessments"][0]["due_date"] == "2026-09-18"
    assert after["course"]["end_date"] == "2026-09-23"


def test_move_assessment_due():
    after = apply_operations(
        sample_state(),
        [MoveAssessmentDue(op="move_assessment_due", assessment_id=2, new_due_date="2026-09-25")],
    )
    a2 = next(a for a in after["assessments"] if a["id"] == 2)
    assert a2["due_date"] == "2026-09-25"


def test_move_unknown_assessment_raises():
    with pytest.raises(OperationError):
        apply_operations(
            sample_state(),
            [MoveAssessmentDue(op="move_assessment_due", assessment_id=99, new_due_date="2026-09-25")],
        )


def test_add_quiz_after_recursion_lecture():
    # "Add a quiz after the recursion lecture" -> quiz on the next meeting (Sorting, id 3).
    after = apply_operations(
        sample_state(),
        [AddAssessment(op="add_assessment", kind="quiz", title="Quiz 1", after_meeting_id=2)],
    )
    quiz = next(a for a in after["assessments"] if a["title"] == "Quiz 1")
    assert quiz["kind"] == "quiz"
    assert quiz["due_date"] == "2026-09-14"
    assert quiz["linked_meeting_id"] == 3
    assert quiz["id"] < 0  # temp id for a new entity


def test_cancel_meeting_reshuffles_content():
    # Cancel "Sorting" (id 3); its topic pushes into the next slot, "Trees" overflows.
    after = apply_operations(
        sample_state(),
        [CancelMeeting(op="cancel_meeting", meeting_id=3, reshuffle_content=True)],
    )
    m3 = next(m for m in after["meetings"] if m["id"] == 3)
    assert m3["status"] == "canceled"
    assert m3["topics"] == []
    # one extra meeting created to absorb the overflow
    assert len(after["meetings"]) == 5
    m4 = next(m for m in after["meetings"] if m["id"] == 4)
    assert m4["topics"] == ["sorting"]
    new_meetings = [m for m in after["meetings"] if m["id"] < 0]
    assert len(new_meetings) == 1 and new_meetings[0]["topics"] == ["trees"]


def test_cancel_meeting_without_reshuffle_keeps_content():
    after = apply_operations(
        sample_state(),
        [CancelMeeting(op="cancel_meeting", meeting_id=3, reshuffle_content=False)],
    )
    m3 = next(m for m in after["meetings"] if m["id"] == 3)
    assert m3["status"] == "canceled"
    assert m3["topics"] == ["sorting"]  # untouched
    assert len(after["meetings"]) == 4


def test_shift_topics_by_two_meetings():
    # "Delay all class topics by one week" (Mon/Wed = 2 meetings/week).
    after = apply_operations(sample_state(), [ShiftTopics(op="shift_topics", by_meetings=2)])
    by_pos = sorted(after["meetings"], key=lambda m: m["position"])
    assert by_pos[0]["topics"] == []  # first two meetings now empty
    assert by_pos[1]["topics"] == []
    assert by_pos[2]["topics"] == ["intro"]  # content pushed down 2 slots
    assert by_pos[2]["readings"][0]["title"] == "Ch1"  # readings move with topics
    assert len(after["meetings"]) == 6  # two new meetings absorb overflow
    # dates of the original meetings are unchanged
    assert by_pos[0]["date"] == "2026-09-07"


def test_compute_diff_reports_changes():
    before = sample_state()
    after = apply_operations(before, [MoveAssessmentDue(op="move_assessment_due", assessment_id=2, new_due_date="2026-09-25")])
    diff = compute_diff(before, after)
    assert any(c["type"] == "assessment_moved" for c in diff)


def test_operation_set_schema_builds():
    # The JSON schema is handed to the LLM as a tool — it must serialize.
    schema = OperationSet.model_json_schema()
    assert "properties" in schema and "operations" in schema["properties"]
