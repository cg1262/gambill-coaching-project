from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "viewer"):
    def _inner():
        return Session(username="coach-review", role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_open_submissions_returns_non_completed_items(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")

    monkeypatch.setattr(
        main,
        "list_coaching_intake_submissions",
        lambda workspace_id, limit=50: [
            {"submission_id": "sub-1", "workspace_id": workspace_id, "applicant_name": "A"},
            {"submission_id": "sub-2", "workspace_id": workspace_id, "applicant_name": "B"},
        ],
    )

    def _latest(submission_id):
        return {"submission_id": submission_id, "run_status": "needs_review" if submission_id == "sub-1" else "completed"}

    monkeypatch.setattr(main, "get_latest_coaching_generation_run", _latest)

    client = TestClient(app)
    res = client.get("/coaching/review/open-submissions", params={"workspace_id": "ws-1"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["total"] == 1
    assert body["open_submissions"][0]["submission"]["submission_id"] == "sub-1"
    app.dependency_overrides = {}


def test_review_submission_runs_returns_runs(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1"})
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=20: [{"run_id": "run-1", "run_status": "needs_review"}])

    client = TestClient(app)
    res = client.get("/coaching/review/submissions/sub-1/runs", params={"limit": 10})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["total"] == 1
    assert body["runs"][0]["run_id"] == "run-1"
    app.dependency_overrides = {}
