import hashlib
import hmac
import json
import time
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app
from rate_limits import RATE_LIMIT_POLICIES_DEFAULT, RATE_LIMIT_STORE


def _override_session(role: str = "editor", username: str = "tester"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _reset_policies_to_defaults():
    payload = {
        "policies": {
            name: {
                "rules": [
                    {
                        "limit": rule.limit,
                        "window_seconds": rule.window_seconds,
                        "burst": rule.burst,
                    }
                    for rule in policy.rules
                ]
            }
            for name, policy in RATE_LIMIT_POLICIES_DEFAULT.items()
        }
    }
    main.rate_limit_policy_update(payload)


def setup_function():
    _reset_policies_to_defaults()
    RATE_LIMIT_STORE.reset()
    app.dependency_overrides = {}


def test_auth_rate_limit_uses_ip_burst(monkeypatch):
    monkeypatch.setattr(main, "get_user_auth", lambda username, password: None)
    monkeypatch.setattr(main, "lakebase_is_configured", lambda: True)
    client = TestClient(app)

    for _ in range(20):
        res = client.post("/auth/login", json={"username": "u", "password": "bad"})
        assert res.status_code == 200

    blocked = client.post("/auth/login", json={"username": "u", "password": "bad"})
    assert blocked.status_code == 429
    assert blocked.json().get("code") in {"rate_limit_exceeded", "rate_limited"}


def test_generation_rate_limit_user_window(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach1")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_name": "A", "preferences_json": {}, "resume_text": "", "self_assessment_text": "", "applicant_email": "a@x.com"})
    monkeypatch.setattr(main, "generate_sow_with_llm", lambda intake, parsed_jobs: {"ok": True, "sow": main.build_sow_skeleton(intake, parsed_jobs), "meta": {"usage": {"total_tokens": 500}}})
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_recent_coaching_feedback_events", lambda submission_id, limit=3: [])

    client = TestClient(app)
    for _ in range(5):
        ok = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []})
        assert ok.status_code == 200

    blocked = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []})
    assert blocked.status_code == 429


def _webhook_headers(secret: str, body: bytes, ts: int | None = None) -> dict[str, str]:
    timestamp = int(ts or time.time())
    digest = hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode("utf-8") + body, hashlib.sha256).hexdigest()
    return {
        "x-webhook-provider": "squarespace",
        "x-webhook-timestamp": str(timestamp),
        "x-webhook-signature": digest,
    }


def test_webhook_rejects_unsigned(monkeypatch):
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_test")
    client = TestClient(app)
    payload = {
        "id": "evt_1",
        "workspace_id": "ws-1",
        "email": "member@example.com",
        "subscription_status": "active",
    }
    res = client.post("/coaching/subscription/webhook", json=payload)
    assert res.status_code == 403


def test_webhook_signature_accepts_and_keeps_idempotency(monkeypatch):
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_test")
    calls = {"save": 0, "upsert": 0}
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: calls.__setitem__("save", calls["save"] + 1))
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: calls.__setitem__("upsert", calls["upsert"] + 1))
    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: {"event_id": event_id, "payload_json": {"subscription_status": "active"}} if calls["save"] > 0 else None)

    client = TestClient(app)
    payload = {
        "id": "evt_2",
        "workspace_id": "ws-1",
        "provider": "squarespace",
        "event_type": "subscription.updated",
        "email": "member@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
    }
    body = json.dumps(payload).encode("utf-8")
    headers = _webhook_headers("whsec_test", body)

    first = client.post("/coaching/subscription/webhook", content=body, headers={**headers, "content-type": "application/json"})
    assert first.status_code == 200
    assert first.json()["idempotent_replay"] is False

    second = client.post("/coaching/subscription/webhook", content=body, headers={**headers, "content-type": "application/json"})
    assert second.status_code == 200
    assert second.json()["idempotent_replay"] is True
    assert calls["save"] == 1
    assert calls["upsert"] == 1
