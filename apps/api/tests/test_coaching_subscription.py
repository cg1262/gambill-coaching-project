from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from config import settings
from db_lakebase import get_coaching_account_subscription, upsert_coaching_account_subscription
from main import app
from rate_limits import RATE_LIMIT_POLICIES_DEFAULT, RATE_LIMIT_STORE


def _override_session(role: str = "viewer", username: str = "tester"):
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


def test_subscription_lifecycle_readiness(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "viewer1")
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "renewal_date": "2026-04-01", "plan_tier": "core"},
    )
    monkeypatch.setattr(
        main,
        "list_recent_coaching_subscription_events",
        lambda workspace_id, email=None, limit=10: [{"event_id": "evt_1", "event_type": "subscription.updated", "provider": "stripe", "received_at": "2026-03-01T00:00:00Z", "payload_json": {"subscription_status": "active", "signature": "whsec_secret"}}],
    )

    client = TestClient(app)
    res = client.get("/coaching/subscription/lifecycle-readiness", params={"workspace_id": "ws-1", "email": "test@example.com"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["checks"]["status_consistent_with_last_event"] is True
    assert body["checks"]["event_stream_present"] is True

    evt = body["recent_events"][0]
    assert evt["event_id"] == "evt_1"
    assert evt["status"] == "active"
    assert "payload_json" not in evt
    assert "signature" not in str(body).lower()
    app.dependency_overrides = {}


def test_subscription_sync_stub(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")

    calls = {"event": 0, "account": 0}

    def _save_event(**kwargs):
        calls["event"] += 1

    def _upsert_account(**kwargs):
        calls["account"] += 1
        assert kwargs["subscription_status"] == "active"
        assert kwargs["username"] == "coach-admin"

    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: None)
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
    assert body["idempotent_replay"] is False
    app.dependency_overrides = {}


def test_subscription_sync_allows_explicit_username_override(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")

    captured: dict[str, str | None] = {}
    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: None)
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: None)

    def _upsert_account(**kwargs):
        captured["username"] = kwargs["username"]
        captured["email"] = kwargs["email"]

    monkeypatch.setattr(main, "upsert_coaching_account_subscription", _upsert_account)

    client = TestClient(app)
    res = client.post(
        "/coaching/subscription/sync",
        json={
            "workspace_id": "ws-1",
            "provider": "squarespace",
            "event_type": "subscription.updated",
            "email": "demo@example.com",
            "username": "admin",
            "plan_tier": "pro",
            "subscription_status": "active",
            "raw_event": {"id": "evt_demo_sync"},
        },
    )

    assert res.status_code == 200
    assert res.json()["active"] is True
    assert captured["username"] == "admin"
    assert captured["email"] == "demo@example.com"
    app.dependency_overrides = {}


def test_subscription_sync_is_idempotent_on_replay(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")

    monkeypatch.setattr(
        main,
        "get_coaching_subscription_event",
        lambda event_id: {"event_id": event_id, "payload_json": {"subscription_status": "active"}},
    )

    calls = {"event": 0, "account": 0}
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: calls.__setitem__("event", calls["event"] + 1))
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: calls.__setitem__("account", calls["account"] + 1))

    client = TestClient(app)
    res = client.post(
        "/coaching/subscription/sync",
        json={
            "workspace_id": "ws-1",
            "provider": "stripe",
            "event_type": "customer.subscription.updated",
            "email": "test@example.com",
            "plan_tier": "core",
            "subscription_status": "inactive",
            "raw_event": {"id": "evt_dupe"},
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["idempotent_replay"] is True
    assert body["status"] == "active"
    assert body["active"] is True
    assert calls["event"] == 0
    assert calls["account"] == 0
    app.dependency_overrides = {}


def test_subscription_account_upsert_persists_in_duckdb(tmp_path):
    original_backend = settings.lakebase_backend
    original_path = settings.lakebase_duckdb_path
    try:
        settings.lakebase_backend = "duckdb"
        settings.lakebase_duckdb_path = str(tmp_path / "coaching-subscriptions.duckdb")

        upsert_coaching_account_subscription(
            workspace_id="ws-demo",
            username="admin",
            email="candidate@example.com",
            plan_tier="starter",
            subscription_status="active",
            renewal_date=None,
            provider_customer_id=None,
            provider_subscription_id=None,
            provider_source="squarespace",
            updated_by="admin",
        )

        account = get_coaching_account_subscription("ws-demo", username="admin")
        assert account is not None
        assert account["email"] == "candidate@example.com"
        assert account["subscription_status"] == "active"
    finally:
        settings.lakebase_backend = original_backend
        settings.lakebase_duckdb_path = original_path
