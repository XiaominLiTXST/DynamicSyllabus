import os

os.environ["DATABASE_URL"] = "sqlite:///./syllabus_api_test.db"
os.environ["ADMIN_PASSWORD"] = "changeme"
os.environ["SESSION_SECRET"] = "test-secret"
os.environ["LLM_PROVIDER"] = "openai"
os.environ["OPENAI_API_KEY"] = ""  # force the stub provider

for _path in ("syllabus_api_test.db",):
    try:
        os.remove(_path)
    except FileNotFoundError:
        pass

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def auth(client):
    r = client.post("/api/login", json={"password": "changeme"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture(scope="module")
def course(client, auth):
    r = client.post(
        "/api/courses",
        headers=auth,
        json={
            "title": "CS 250",
            "term": "Fall 2026",
            "instructor": "Prof. Lee",
            "meeting_days": ["Mon", "Wed"],
            "start_date": "2026-09-07",
            "end_date": "2026-09-16",
            "excluded_dates": [],
        },
    )
    assert r.status_code == 200
    return r.json()


def test_requires_auth(client):
    assert client.get("/api/courses").status_code == 401


def test_course_generates_meetings(course):
    assert len(course["meetings"]) == 4
    assert course["meetings"][0]["date"] == "2026-09-07"
    assert course["course"]["public_token"] == "cs250fall2026"


def test_apply_move_then_undo(client, auth, course):
    cid = course["course"]["id"]
    # Add an assessment manually, then move it via an apply (simulating an LLM op).
    r = client.post(
        f"/api/courses/{cid}/assessments",
        headers=auth,
        json={"kind": "assignment", "title": "Assignment 2", "due_date": "2026-09-14"},
    )
    aid = r.json()["id"]

    r = client.post(
        f"/api/courses/{cid}/apply",
        headers=auth,
        json={
            "operations": [
                {"op": "move_assessment_due", "assessment_id": aid, "new_due_date": "2026-09-21"}
            ],
            "user_message": "move assignment 2 to the 21st",
        },
    )
    assert r.status_code == 200
    moved = next(a for a in r.json()["state"]["assessments"] if a["id"] == aid)
    assert moved["due_date"] == "2026-09-21"

    # Undo restores the original due date.
    r = client.post(f"/api/courses/{cid}/undo", headers=auth)
    assert r.status_code == 200
    restored = next(a for a in r.json()["state"]["assessments"] if a["id"] == aid)
    assert restored["due_date"] == "2026-09-14"


def test_apply_add_quiz_after_meeting_then_undo(client, auth, course):
    cid = course["course"]["id"]
    state = client.get(f"/api/courses/{cid}", headers=auth).json()
    second_meeting = state["meetings"][1]
    third_meeting = state["meetings"][2]

    r = client.post(
        f"/api/courses/{cid}/apply",
        headers=auth,
        json={
            "operations": [
                {
                    "op": "add_assessment",
                    "kind": "quiz",
                    "title": "Quiz 1",
                    "after_meeting_id": second_meeting["id"],
                }
            ]
        },
    )
    assert r.status_code == 200
    new_state = r.json()["state"]
    quiz = next(a for a in new_state["assessments"] if a["title"] == "Quiz 1")
    assert quiz["due_date"] == third_meeting["date"]
    assert quiz["linked_meeting_id"] == third_meeting["id"]

    # Undo removes the quiz entirely.
    r = client.post(f"/api/courses/{cid}/undo", headers=auth)
    titles = [a["title"] for a in r.json()["state"]["assessments"]]
    assert "Quiz 1" not in titles


def test_public_view(client, course):
    token = course["course"]["public_token"]
    r = client.get(f"/api/public/{token}")
    assert r.status_code == 200
    data = r.json()
    assert "public_token" not in data["course"]  # not leaked
    assert len(data["meetings"]) >= 4
    assert data["next_class"] is not None  # course is in the future


def test_chat_without_key_asks_to_configure(client, auth, course):
    cid = course["course"]["id"]
    r = client.post(
        f"/api/courses/{cid}/chat",
        headers=auth,
        json={"message": "delay everything a week"},
    )
    assert r.status_code == 200
    assert r.json()["needs_clarification"]  # stub provider reports not configured
    assert "AI editing isn't configured" in r.json()["needs_clarification"]
    assert r.json()["operations"] == []
