from datetime import datetime, timezone
import json
import time

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


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
