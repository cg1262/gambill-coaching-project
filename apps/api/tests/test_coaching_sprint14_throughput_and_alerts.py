from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "admin", username: str = "coach-s14"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_sprint14_batch_review_status_endpoint_updates_multiple(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("admin", "coach-s14")
    monkeypatch.setattr(main, "_apply_rate_limit", lambda **kwargs: None)
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "applicant_email": "x@example.com"})
    monkeypatch.setattr(
        main,
        "_persist_review_state_with_retry",
        lambda **kwargs: {"ok": True, "attempts": 1, "submission": {"submission_id": kwargs["submission_id"], "coach_review_status": kwargs["coach_review_status"]}},
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/review/batch-status",
        json={"workspace_id": "ws-1", "submission_ids": ["sub-1", "sub-2"], "coach_review_status": "in_review", "coach_notes": "batch"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["updated"] == 2
    assert body["counts"]["failed"] == 0

    app.dependency_overrides = {}


def test_sprint14_batch_regenerate_returns_per_submission_runs(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("admin", "coach-s14")
    monkeypatch.setattr(main, "_apply_rate_limit", lambda **kwargs: None)

    def _fake_generate(req, request, session):
        return {
            "ok": True,
            "run_id": f"run-{req.submission_id}",
            "quality": {"score": 88},
            "findings": [],
            "quality_flags": {"hard_quality_gate_triggered": False},
        }

    monkeypatch.setattr(main, "coaching_generate_sow", _fake_generate)

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/batch-regenerate",
        json={"workspace_id": "ws-1", "submission_ids": ["sub-1", "sub-2"], "parsed_jobs": [], "regenerate_with_improvements": True},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["completed"] == 2
    assert body["runs"][0]["run_id"].startswith("run-sub-")

    app.dependency_overrides = {}


def test_sprint14_invalid_signature_alerts_are_operationally_visible(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("admin", "coach-s14")
    monkeypatch.setenv("WEBHOOK_INVALID_SIG_ALERT_THRESHOLD", "1")
    monkeypatch.setattr(main, "dispatch_invalid_webhook_signature_alert", lambda payload: True)

    main._record_invalid_webhook_signature_attempt(
        provider="squarespace",
        source_ip="127.0.0.1",
        route="/coaching/subscription/webhook",
        reason="bad_signature",
        actor="coach-s14",
        role="admin",
    )

    client = TestClient(app)
    res = client.get("/admin/security/webhook-alerts", params={"limit": 10})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] >= 1
    assert body["alerts"][0]["route"] == "/coaching/subscription/webhook"

    app.dependency_overrides = {}
