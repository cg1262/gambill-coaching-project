from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app
from rate_limits import RATE_LIMIT_STORE


def _override_session(role: str = "editor", username: str = "sprint7"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def setup_function():
    RATE_LIMIT_STORE.reset()
    app.dependency_overrides = {}


def test_subscription_sync_derives_idempotency_key_without_event_id(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")

    saved = {}
    calls = {"save": 0, "upsert": 0}

    def _get_event(event_id: str):
        return saved.get(event_id)

    def _save_event(**kwargs):
        calls["save"] += 1
        saved[kwargs["event_id"]] = {"event_id": kwargs["event_id"], "payload_json": kwargs.get("payload") or {}}

    monkeypatch.setattr(main, "get_coaching_subscription_event", _get_event)
    monkeypatch.setattr(main, "save_coaching_subscription_event", _save_event)
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: calls.__setitem__("upsert", calls["upsert"] + 1))

    client = TestClient(app)
    payload = {
        "workspace_id": "ws-1",
        "provider": "squarespace",
        "event_type": "subscription.updated",
        "email": "member@example.com",
        "plan_tier": "coaching-core",
        "subscription_status": "active",
        "raw_event": {"kind": "status-sync", "attempt": 1},
    }

    first = client.post("/coaching/subscription/sync", json=payload)
    assert first.status_code == 200
    first_body = first.json()
    assert first_body["idempotent_replay"] is False
    assert first_body["idempotency_key_source"] == "derived"
    assert str(first_body["event_id"]).startswith("derived_")

    second = client.post("/coaching/subscription/sync", json=payload)
    assert second.status_code == 200
    second_body = second.json()
    assert second_body["idempotent_replay"] is True
    assert second_body["event_id"] == first_body["event_id"]

    assert calls["save"] == 1
    assert calls["upsert"] == 1


def test_subscription_routes_obey_rate_limit_policy_and_admin_override(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("admin", "ops-admin")
    monkeypatch.setattr(main, "get_coaching_account_subscription", lambda workspace_id, username=None, email=None: {"subscription_status": "active", "plan_tier": "core"})

    client = TestClient(app)

    snapshot = client.get("/admin/security/rate-limits")
    assert snapshot.status_code == 200
    assert "subscription" in snapshot.json()["policies"]
    original = snapshot.json()

    try:
        # Tighten policy for deterministic 429 verification
        updated = client.put(
            "/admin/security/rate-limits",
            json={
                "policies": {
                    "subscription": {
                        "rules": [
                            {"limit": 1, "window_seconds": 60, "burst": 1},
                            {"limit": 100, "window_seconds": 60, "burst": 100},
                        ]
                    }
                }
            },
        )
        assert updated.status_code == 200
        assert updated.json()["policies"]["subscription"]["rules"][0]["limit"] == 1

        ok = client.get("/coaching/subscription/status", params={"workspace_id": "ws-1"})
        assert ok.status_code == 200

        limited = client.get("/coaching/subscription/status", params={"workspace_id": "ws-1"})
        assert limited.status_code == 429
        body = limited.json()
        assert body["code"] == "rate_limited"
    finally:
        client.put("/admin/security/rate-limits", json={"policies": original.get("policies", {})})


def test_controlled_pilot_trace_preserves_conversion_and_feedback_integrity(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-runner")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})

    submissions = {}
    conversion_events = []
    feedback_events = []

    def _save_intake(**kwargs):
        submissions[kwargs["submission_id"]] = {
            "submission_id": kwargs["submission_id"],
            "workspace_id": kwargs["workspace_id"],
            "applicant_name": kwargs["applicant_name"],
            "applicant_email": kwargs["applicant_email"],
            "resume_text": kwargs["resume_text"],
            "self_assessment_text": kwargs["self_assessment_text"],
            "job_links_json": kwargs.get("job_links") or [],
            "preferences_json": kwargs.get("preferences") or {},
        }

    monkeypatch.setattr(main, "save_coaching_intake_submission", _save_intake)
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: submissions.get(submission_id))
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(main, "generate_sow_with_llm", lambda intake, parsed_jobs: {"ok": True, "sow": main.build_sow_skeleton(intake, parsed_jobs), "meta": {"provider": "scaffold"}})
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: conversion_events.append(kwargs))
    monkeypatch.setattr(main, "save_coaching_feedback_event", lambda **kwargs: feedback_events.append(kwargs))
    monkeypatch.setattr(main, "list_recent_coaching_feedback_events", lambda submission_id, limit=3: [])

    client = TestClient(app)

    intake = client.post(
        "/coaching/intake",
        json={
            "workspace_id": "ws-1",
            "applicant_name": "Pilot Candidate",
            "applicant_email": "pilot@example.com",
            "resume_text": "resume",
            "self_assessment_text": "self assessment",
            "job_links": ["https://example.org/job/1"],
            "preferences": {"timeline_weeks": 8},
        },
    )
    assert intake.status_code == 200
    submission_id = intake.json()["submission_id"]

    generate = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": submission_id, "parsed_jobs": []})
    assert generate.status_code == 200
    sow = generate.json()["sow"]

    regenerate = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": submission_id, "parsed_jobs": [], "regenerate_with_improvements": True},
    )
    assert regenerate.status_code == 200

    exported = client.post(
        "/coaching/sow/export",
        json={"workspace_id": "ws-1", "submission_id": submission_id, "format": "json", "sow": sow},
    )
    assert exported.status_code == 200

    feedback = client.post(
        "/coaching/review/feedback",
        json={
            "workspace_id": "ws-1",
            "submission_id": submission_id,
            "review_tags": ["needs_star_depth", "kpi_specificity"],
            "regeneration_hints": ["Quantify KPI impact"],
            "coach_notes": "Add measurable outcomes",
        },
    )
    assert feedback.status_code == 200

    names = [evt.get("event_name") for evt in conversion_events]
    assert "intake_completed" in names
    assert "sow_generated" in names
    assert "sow_regenerated" in names
    assert "sow_exported" in names
    assert "coach_feedback_captured" in names

    assert len(feedback_events) == 1
    assert feedback_events[0]["submission_id"] == submission_id
    assert feedback_events[0]["review_tags"] == ["needs_star_depth", "kpi_specificity"]
