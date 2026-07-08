from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError
from sqlmodel import Session, select

from ..auth import require_admin
from ..db import get_session
from ..llm import get_provider
from ..models import ChangeLog, Course
from ..operations import OperationError, OperationSet, apply_operations, compute_diff
from ..persistence import reconcile
from ..schemas import ApplyRequest, ChatRequest
from ..serialization import load_state

router = APIRouter(prefix="/api", tags=["chat"], dependencies=[Depends(require_admin)])


@router.post("/courses/{course_id}/chat")
def chat(course_id: int, body: ChatRequest, session: Session = Depends(get_session)):
    """Propose changes from a natural-language instruction. Computes a preview diff
    but does NOT commit anything."""
    state = load_state(session, course_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Course not found")

    provider = get_provider()
    try:
        result = provider.propose_operations(
            state, body.message, [m.model_dump() for m in body.history], date.today()
        )
    except Exception as exc:  # noqa: BLE001 — surface provider errors to the UI
        return {
            "explanation": "",
            "needs_clarification": f"The assistant is unavailable: {exc}",
            "operations": [],
            "diff": [],
            "apply_error": None,
        }

    response = {
        "explanation": result.explanation,
        "needs_clarification": result.needs_clarification,
        "operations": [op.model_dump(mode="json") for op in result.operations],
        "diff": [],
        "apply_error": None,
    }
    if result.operations and not result.needs_clarification:
        try:
            after = apply_operations(state, result.operations)
            response["diff"] = compute_diff(state, after)
        except OperationError as exc:
            response["apply_error"] = str(exc)
    return response


@router.post("/courses/{course_id}/apply")
def apply_changes(
    course_id: int, body: ApplyRequest, session: Session = Depends(get_session)
):
    """Commit a previously previewed operation set in a single transaction, recording
    a snapshot for undo."""
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    try:
        opset = OperationSet(operations=body.operations)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid operations: {exc}") from exc

    state = load_state(session, course_id)
    try:
        after = apply_operations(state, opset.operations)
    except OperationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    diff = compute_diff(state, after)
    reconcile(session, course, after)
    log = ChangeLog(
        course_id=course_id,
        user_message=body.user_message,
        summary="; ".join(c["summary"] for c in diff[:6]) or "No visible changes",
        operations=[op.model_dump(mode="json") for op in opset.operations],
        snapshot_before=state,
    )
    session.add(log)
    session.commit()
    return {"state": load_state(session, course_id), "diff": diff, "change_id": log.id}


@router.post("/courses/{course_id}/undo")
def undo(course_id: int, session: Session = Depends(get_session)):
    """Restore the snapshot from the most recent applied change."""
    course = session.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="Course not found")

    log = session.exec(
        select(ChangeLog)
        .where(ChangeLog.course_id == course_id, ChangeLog.undone == False)  # noqa: E712
        .order_by(ChangeLog.id.desc())
    ).first()
    if log is None:
        raise HTTPException(status_code=404, detail="Nothing to undo")

    reconcile(session, course, log.snapshot_before)
    log.undone = True
    session.add(log)
    session.commit()
    return {"state": load_state(session, course_id), "undone_change_id": log.id}


@router.get("/courses/{course_id}/changes")
def list_changes(course_id: int, session: Session = Depends(get_session)):
    logs = session.exec(
        select(ChangeLog)
        .where(ChangeLog.course_id == course_id)
        .order_by(ChangeLog.id.desc())
    ).all()
    return [
        {
            "id": log.id,
            "created_at": log.created_at.isoformat(),
            "user_message": log.user_message,
            "summary": log.summary,
            "undone": log.undone,
        }
        for log in logs
    ]
