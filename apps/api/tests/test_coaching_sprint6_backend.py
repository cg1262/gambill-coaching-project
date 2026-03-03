from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "editor", username: str = "sprint6"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_generate_adds_observability_and_feedback_hints(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_name": "A", "preferences_json": {}, "resume_text": "", "self_assessment_text": "", "applicant_email": "a@x.com"},
    )
    monkeypatch.setattr(main, "generate_sow_with_llm", lambda intake, parsed_jobs: {"ok": False, "sow": main.build_sow_skeleton(intake, parsed_jobs), "meta": {"provider": "scaffold", "usage": {"total_tokens": 1200}}})
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_recent_coaching_feedback_events", lambda submission_id, limit=3: [{"regeneration_hints_json": ["Add stronger KPI linkage"]}])

    client = TestClient(app)
    res = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []})
    assert res.status_code == 200
    body = res.json()
    assert body["observability"]["latency_band"] in {"fast", "moderate", "slow"}
    assert body["observability"]["cost_band"] in {"low", "medium", "high"}
    hints = body["quality"]["quality_diagnostics"]["targeted_regeneration_hints"]
    assert any("KPI" in h for h in hints)
    app.dependency_overrides = {}


def test_review_feedback_capture_endpoint(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_email": "candidate@example.com"})

    calls = {"feedback": 0}
    monkeypatch.setattr(main, "save_coaching_feedback_event", lambda **kwargs: calls.__setitem__("feedback", calls["feedback"] + 1))
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)

    client = TestClient(app)
    res = client.post(
        "/coaching/review/feedback",
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "review_tags": ["needs_star_depth", "portfolio_gap"],
            "regeneration_hints": ["Expand STAR result metrics"],
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert calls["feedback"] == 1
    app.dependency_overrides = {}


def test_conversion_funnel_and_pilot_readiness(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")
    monkeypatch.setattr(main, "get_coaching_account_subscription", lambda workspace_id, username=None, email=None: {"subscription_status": "active"})
    monkeypatch.setattr(main, "list_recent_coaching_subscription_events", lambda workspace_id, email=None, limit=10: [{"event_id": "evt1"}])
    monkeypatch.setattr(
        main,
        "list_recent_coaching_conversion_events",
        lambda workspace_id, submission_id=None, limit=500: [
            {"event_name": "member_launch_verified"},
            {"event_name": "intake_completed"},
            {"event_name": "sow_generated"},
            {"event_name": "sow_exported"},
            {"event_name": "mentoring_intent"},
        ],
    )

    client = TestClient(app)
    funnel = client.get("/coaching/conversion/funnel", params={"workspace_id": "ws-1", "submission_id": "sub-1"})
    assert funnel.status_code == 200
    funnel_counts = {x["event"]: x["count"] for x in funnel.json()["funnel"]}
    assert funnel_counts["sow_generated"] == 1

    ready = client.get("/coaching/pilot/launch-readiness", params={"workspace_id": "ws-1", "submission_id": "sub-1"})
    assert ready.status_code == 200
    body = ready.json()
    assert body["checks"]["subscription_active"] is True
    assert body["checks"]["launch_verification_present"] is True
    assert body["ready"] is True
    app.dependency_overrides = {}


def test_export_includes_interview_ready_sections(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_email": "candidate@example.com"})
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)

    client = TestClient(app)
    sow = main.build_sow_skeleton({"applicant_name": "A", "preferences": {}}, [])
    res = client.post(
        "/coaching/sow/export",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "format": "markdown", "sow": sow},
    )
    assert res.status_code == 200
    content = res.json()["content"]
    assert "Interview-ready STAR Bullets" in content
    assert "Portfolio Checklist" in content
    app.dependency_overrides = {}
