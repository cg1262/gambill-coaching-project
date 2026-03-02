from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "editor"):
    def _inner():
        return Session(username="sprint2", role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_generate_returns_quality_score(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_name": "A", "preferences_json": {}, "resume_text": "", "self_assessment_text": "", "applicant_email": "a@x.com"},
    )
    monkeypatch.setattr(main, "generate_sow_with_llm", lambda intake, parsed_jobs: {"ok": False, "sow": main.build_sow_skeleton(intake, parsed_jobs), "meta": {"provider": "scaffold"}})
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])

    client = TestClient(app)
    res = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []})
    assert res.status_code == 200
    body = res.json()
    assert "quality" in body
    assert isinstance(body["quality"]["score"], int)
    app.dependency_overrides = {}


def test_review_status_update_endpoint(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_email": "a@x.com"})
    monkeypatch.setattr(main, "update_coaching_review_status", lambda submission_id, coach_review_status, coach_notes: None)

    client = TestClient(app)
    res = client.post("/coaching/review/status", json={"workspace_id": "ws-1", "submission_id": "sub-1", "coach_review_status": "in_review", "coach_notes": "looks good"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    app.dependency_overrides = {}


def test_coaching_health_readiness(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")
    monkeypatch.setattr(main, "lakebase_health", lambda: (True, "ok"))

    client = TestClient(app)
    res = client.get("/coaching/health/readiness", params={"workspace_id": "ws-1"})
    assert res.status_code == 200
    assert "readiness" in res.json()
    app.dependency_overrides = {}
