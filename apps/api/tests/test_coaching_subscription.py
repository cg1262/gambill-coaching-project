from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "viewer", username: str = "tester"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_subscription_status_not_found(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "viewer1")
    monkeypatch.setattr(main, "get_coaching_account_subscription", lambda workspace_id, username=None, email=None: None)

    client = TestClient(app)
    res = client.get("/coaching/subscription/status", params={"workspace_id": "ws-1"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["active"] is False
    assert body["status"] == "not_found"
    app.dependency_overrides = {}


def test_subscription_sync_stub(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")

    calls = {"event": 0, "account": 0}

    def _save_event(**kwargs):
        calls["event"] += 1

    def _upsert_account(**kwargs):
        calls["account"] += 1
        assert kwargs["subscription_status"] == "active"

    monkeypatch.setattr(main, "save_coaching_subscription_event", _save_event)
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", _upsert_account)

    client = TestClient(app)
    res = client.post(
        "/coaching/subscription/sync",
        json={
            "workspace_id": "ws-1",
            "provider": "stripe",
            "event_type": "customer.subscription.updated",
            "email": "test@example.com",
            "plan_tier": "core",
            "subscription_status": "trialing",
            "renewal_date": "2026-04-01T00:00:00Z",
            "provider_customer_id": "cus_123",
            "provider_subscription_id": "sub_123",
            "raw_event": {"id": "evt_123"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["active"] is True
    assert body["status"] == "active"
    assert calls["event"] == 1
    assert calls["account"] == 1
    app.dependency_overrides = {}
