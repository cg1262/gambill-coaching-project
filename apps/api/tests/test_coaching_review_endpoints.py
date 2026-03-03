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

    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(
        main,
        "list_coaching_intake_submissions",
        lambda workspace_id, limit=50, review_status=None: [
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


def test_review_approve_send_generates_launch_token(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active", "plan_tier": "pro"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_email": "candidate@example.com"})
    monkeypatch.setattr(main, "get_latest_coaching_generation_run", lambda submission_id: {"run_id": "run-1", "run_status": "completed"})

    monkeypatch.setattr(
        main,
        "_persist_review_state_with_retry",
        lambda **kwargs: {
            "ok": True,
            "attempts": 1,
            "submission": {
                "submission_id": kwargs.get("submission_id"),
                "coach_review_status": kwargs.get("coach_review_status"),
                "coach_notes": kwargs.get("coach_notes") or "",
            },
        },
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/review/approve-send",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "coach_notes": "approved"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["coach_review_status"] == "approved_sent"
    assert body["handoff"]["launch_token"]
    assert body["consistency"]["persist_ok"] is True

    verify = client.post(
        "/coaching/member/launch-token/verify",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "launch_token": body["handoff"]["launch_token"]},
    )
    assert verify.status_code == 200
    assert verify.json()["valid"] is True
    app.dependency_overrides = {}


def test_review_approve_send_requires_completed_latest_run(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active", "plan_tier": "pro"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_email": "candidate@example.com"})
    monkeypatch.setattr(main, "get_latest_coaching_generation_run", lambda submission_id: {"run_id": "run-1", "run_status": "needs_review"})

    client = TestClient(app)
    res = client.post(
        "/coaching/review/approve-send",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "coach_notes": "approved"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert body["latest_run_status"] == "needs_review"
    app.dependency_overrides = {}


def test_persist_review_state_with_retry_recovers_transient_failure(monkeypatch):
    calls = {"count": 0}

    def _flaky_update(**kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise RuntimeError("transient db write failure")

    monkeypatch.setattr(main, "update_coaching_review_status", _flaky_update)
    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {
            "submission_id": submission_id,
            "coach_review_status": "in_review",
            "coach_notes": "retry ok",
        },
    )

    result = main._persist_review_state_with_retry(
        submission_id="sub-1",
        coach_review_status="in_review",
        coach_notes="retry ok",
        max_attempts=3,
        backoff_sec=0,
    )
    assert result["ok"] is True
    assert result["attempts"] == 2


def test_review_submission_runs_returns_runs(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
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
