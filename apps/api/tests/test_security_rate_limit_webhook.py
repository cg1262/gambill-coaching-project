from datetime import datetime, timezone
import json
import time

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app
from rate_limits import RATE_LIMIT_POLICIES_DEFAULT, RATE_LIMIT_STORE
from webhook_alerts import INVALID_WEBHOOK_SIGNATURE_TRACKER


def _override_session(role: str = "editor", username: str = "security-tester"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_limit(policy_name: str, limit: int = 1, window_sec: int = 60):
    snapshot = main.rate_limit_policy_snapshot()
    rules = snapshot["policies"][policy_name]["rules"]
    patch_rules = []
    for rule in rules:
        patch = {"limit": limit, "window_seconds": window_sec}
        if rule.get("burst") is not None:
            patch["burst"] = limit
        patch_rules.append(patch)
    main.rate_limit_policy_update({"policies": {policy_name: {"rules": patch_rules}}})


def _sign_sync_payload(payload: dict, ts: int, secret: str) -> str:
    req = main.CoachingSubscriptionSyncRequest(**payload)
    body = req.model_dump(mode="json", exclude={"webhook_signature", "webhook_timestamp"})
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return main.hmac.new(secret.encode("utf-8"), f"{ts}.".encode("utf-8") + body_bytes, main.hashlib.sha256).hexdigest()


def _webhook_sig(secret: str, body: bytes, ts: int) -> str:
    return main.hmac.new(secret.encode("utf-8"), f"{ts}.".encode("utf-8") + body, main.hashlib.sha256).hexdigest()


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
    INVALID_WEBHOOK_SIGNATURE_TRACKER._attempts.clear()


def test_auth_login_rate_limit_returns_generic_payload(monkeypatch):
    _set_limit("auth", limit=1)
    monkeypatch.setattr(main, "lakebase_is_configured", lambda: True)
    monkeypatch.setattr(main, "get_user_auth", lambda u, p: None)

    client = TestClient(app)
    first = client.post("/auth/login", json={"username": "u", "password": "bad"})
    assert first.status_code == 200

    second = client.post("/auth/login", json={"username": "u", "password": "bad"})
    assert second.status_code == 429
    body = second.json()
    assert body["code"] == "rate_limited"
    assert body["auth_required"] is False
    assert "token" not in str(body).lower()


def test_generate_review_export_rate_limits_are_generic(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "workspace_id": "ws-1", "applicant_email": "member@example.com", "applicant_name": "User", "preferences_json": {}, "resume_text": "", "self_assessment_text": ""})
    monkeypatch.setattr(main, "generate_sow_with_llm", lambda intake, parsed_jobs: {"ok": True, "sow": main.build_sow_skeleton(intake, parsed_jobs), "meta": {}})
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_recent_coaching_feedback_events", lambda submission_id, limit=3: [])
    monkeypatch.setattr(main, "save_coaching_feedback_event", lambda **kwargs: None)

    client = TestClient(app)

    for policy, path, payload in [
        ("generation", "/coaching/sow/generate", {"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []}),
        ("review_actions", "/coaching/review/feedback", {"workspace_id": "ws-1", "submission_id": "sub-1", "review_tags": ["needs_depth"]}),
        ("exports", "/coaching/sow/export", {"workspace_id": "ws-1", "submission_id": "sub-1", "format": "markdown", "sow": main.build_sow_skeleton({"applicant_name": "User"}, [])}),
    ]:
        _set_limit(policy, limit=1)
        ok = client.post(path, json=payload)
        assert ok.status_code == 200
        denied = client.post(path, json=payload)
        assert denied.status_code == 429
        body = denied.json()
        assert body["code"] == "rate_limited"
        assert body["subscription_required"] is False
        assert "policy" not in body
        assert "rule" not in body
        assert "retry_after_seconds" not in body

    app.dependency_overrides = {}


def test_subscription_webhook_signature_valid_invalid_missing_replay_and_window(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_test_secret")

    calls = {"event": 0, "account": 0}
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: calls.__setitem__("event", calls["event"] + 1))
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: calls.__setitem__("account", calls["account"] + 1))

    base_payload = {
        "workspace_id": "ws-1",
        "provider": "stripe",
        "event_type": "customer.subscription.updated",
        "email": "test@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
        "raw_event": {"id": "evt_sig_1"},
    }

    client = TestClient(app)
    ts = int(time.time())
    valid_sig = _sign_sync_payload(base_payload, ts, "whsec_test_secret")

    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: None)
    valid = client.post("/coaching/subscription/sync", json={**base_payload, "webhook_timestamp": ts, "webhook_signature": valid_sig})
    assert valid.status_code == 200

    invalid = client.post("/coaching/subscription/sync", json={**base_payload, "raw_event": {"id": "evt_sig_2"}, "webhook_timestamp": ts, "webhook_signature": "bad"})
    assert invalid.status_code == 403
    assert invalid.json()["code"] == "forbidden"

    missing = client.post("/coaching/subscription/sync", json={**base_payload, "raw_event": {"id": "evt_sig_3"}, "webhook_timestamp": ts})
    assert missing.status_code == 403
    assert "signature" not in json.dumps(missing.json()).lower()

    old_ts = ts - 3600
    old_sig = _sign_sync_payload({**base_payload, "raw_event": {"id": "evt_sig_4"}}, old_ts, "whsec_test_secret")
    old = client.post("/coaching/subscription/sync", json={**base_payload, "raw_event": {"id": "evt_sig_4"}, "webhook_timestamp": old_ts, "webhook_signature": old_sig})
    assert old.status_code == 403

    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: {"event_id": event_id, "payload_json": {"subscription_status": "active"}})
    replay = client.post("/coaching/subscription/sync", json={**base_payload, "raw_event": {"id": "evt_sig_replay"}, "webhook_timestamp": ts, "webhook_signature": _sign_sync_payload({**base_payload, "raw_event": {"id": "evt_sig_replay"}}, ts, "whsec_test_secret")})
    assert replay.status_code == 200
    assert replay.json()["idempotent_replay"] is True

    assert calls["event"] == 1
    assert calls["account"] == 1
    app.dependency_overrides = {}


def test_subscription_status_and_sync_rate_limits_are_generic(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")
    monkeypatch.setattr(main, "get_coaching_account_subscription", lambda **kwargs: None)

    _set_limit("subscription", limit=1)
    client = TestClient(app)

    ok_status = client.get("/coaching/subscription/status", params={"workspace_id": "ws-1", "email": "member@example.com"})
    assert ok_status.status_code == 200

    denied_status = client.get("/coaching/subscription/status", params={"workspace_id": "ws-1", "email": "member@example.com"})
    assert denied_status.status_code == 429
    denied_status_body = denied_status.json()
    assert denied_status_body["code"] == "rate_limited"
    assert denied_status_body["subscription_required"] is False
    assert "policy" not in denied_status_body
    assert "rule" not in denied_status_body
    assert "retry_after_seconds" not in denied_status_body

    RATE_LIMIT_STORE.reset()
    _set_limit("subscription", limit=1)
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_test_secret")
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: None)
    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: None)

    ts = int(time.time())
    sync_payload = {
        "workspace_id": "ws-1",
        "provider": "stripe",
        "event_type": "customer.subscription.updated",
        "email": "test@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
        "raw_event": {"id": "evt_sync_rl_1"},
    }
    sig = _sign_sync_payload(sync_payload, ts, "whsec_test_secret")

    ok_sync = client.post("/coaching/subscription/sync", json={**sync_payload, "webhook_timestamp": ts, "webhook_signature": sig})
    assert ok_sync.status_code == 200

    denied_sync = client.post("/coaching/subscription/sync", json={**sync_payload, "raw_event": {"id": "evt_sync_rl_2"}, "webhook_timestamp": ts, "webhook_signature": _sign_sync_payload({**sync_payload, "raw_event": {"id": "evt_sync_rl_2"}}, ts, "whsec_test_secret")})
    assert denied_sync.status_code == 429
    denied_sync_body = denied_sync.json()
    assert denied_sync_body["code"] == "rate_limited"
    assert denied_sync_body["subscription_required"] is False
    assert "policy" not in denied_sync_body
    assert "rule" not in denied_sync_body
    assert "retry_after_seconds" not in denied_sync_body

    app.dependency_overrides = {}


def test_subscription_webhook_timestamp_and_signature_checks(monkeypatch):
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_test")
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: None)
    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: None)

    client = TestClient(app)
    payload = {
        "id": "evt_wh_1",
        "workspace_id": "ws-1",
        "provider": "squarespace",
        "event_type": "subscription.updated",
        "email": "member@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    now_ts = int(time.time())

    stale_ts = now_ts - 3600
    stale_headers = {
        "x-webhook-provider": "squarespace",
        "x-webhook-timestamp": str(stale_ts),
        "x-webhook-signature": _webhook_sig("whsec_test", body, stale_ts),
        "content-type": "application/json",
    }
    stale = client.post("/coaching/subscription/webhook", content=body, headers=stale_headers)
    assert stale.status_code == 403
    assert stale.json()["code"] == "forbidden"

    RATE_LIMIT_STORE.reset()

    bad_headers = {
        "x-webhook-provider": "squarespace",
        "x-webhook-timestamp": str(now_ts),
        "x-webhook-signature": "bad",
        "content-type": "application/json",
    }
    bad = client.post("/coaching/subscription/webhook", content=body, headers=bad_headers)
    assert bad.status_code == 403
    assert bad.json()["code"] == "forbidden"


def test_no_sensitive_leak_in_webhook_rejection_logs(monkeypatch, caplog):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_super_secret")

    payload = {
        "workspace_id": "ws-1",
        "provider": "stripe",
        "event_type": "customer.subscription.updated",
        "email": "test@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
        "raw_event": {"id": "evt_log_1"},
        "webhook_timestamp": int(time.time()),
        "webhook_signature": "whsec_super_secret_signature_value",
    }

    client = TestClient(app)
    with caplog.at_level("WARNING"):
        res = client.post("/coaching/subscription/sync", json=payload)

    assert res.status_code == 403
    joined = "\n".join(x.message for x in caplog.records)
    assert "whsec_super_secret" not in joined
    assert "signature_value" not in joined
    app.dependency_overrides = {}


def test_invalid_signature_alert_emits_after_threshold_sync(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-admin")
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_alert_secret")
    monkeypatch.setenv("WEBHOOK_INVALID_SIG_ALERT_THRESHOLD", "2")
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: None)
    monkeypatch.setattr(main, "get_coaching_subscription_event", lambda event_id: None)

    calls: list[tuple[str, dict]] = []

    def _capture_error(msg, *args, **kwargs):
        calls.append((msg, kwargs.get("extra") or {}))

    monkeypatch.setattr(main.logger, "error", _capture_error)

    payload = {
        "workspace_id": "ws-1",
        "provider": "stripe",
        "event_type": "customer.subscription.updated",
        "email": "test@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
        "raw_event": {"id": "evt_alert_sync_1"},
        "webhook_timestamp": int(time.time()),
        "webhook_signature": "bad",
    }

    client = TestClient(app)
    r1 = client.post("/coaching/subscription/sync", json=payload)
    r2 = client.post("/coaching/subscription/sync", json={**payload, "raw_event": {"id": "evt_alert_sync_2"}})

    assert r1.status_code == 403
    assert r2.status_code == 403
    alerts = [extra for msg, extra in calls if msg == "coaching_webhook_invalid_signature_alert"]
    assert len(alerts) == 1
    assert alerts[0].get("route") == "/coaching/subscription/sync"
    app.dependency_overrides = {}


def test_invalid_signature_alert_emits_after_threshold_webhook(monkeypatch):
    monkeypatch.setenv("COACHING_WEBHOOK_SECRET", "whsec_alert_secret")
    monkeypatch.setenv("WEBHOOK_INVALID_SIG_ALERT_THRESHOLD", "2")

    calls: list[tuple[str, dict]] = []

    def _capture_error(msg, *args, **kwargs):
        calls.append((msg, kwargs.get("extra") or {}))

    monkeypatch.setattr(main.logger, "error", _capture_error)

    payload = {
        "id": "evt_wh_alert_1",
        "workspace_id": "ws-1",
        "provider": "squarespace",
        "event_type": "subscription.updated",
        "email": "member@example.com",
        "plan_tier": "core",
        "subscription_status": "active",
    }
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    now_ts = int(time.time())
    bad_headers = {
        "x-webhook-provider": "squarespace",
        "x-webhook-timestamp": str(now_ts),
        "x-webhook-signature": "bad",
        "content-type": "application/json",
    }

    client = TestClient(app)
    r1 = client.post("/coaching/subscription/webhook", content=body, headers=bad_headers)
    r2 = client.post("/coaching/subscription/webhook", content=body, headers=bad_headers)

    assert r1.status_code == 403
    assert r2.status_code == 403
    alerts = [extra for msg, extra in calls if msg == "coaching_webhook_invalid_signature_alert"]
    assert len(alerts) == 1
    assert alerts[0].get("route") == "/coaching/subscription/webhook"
