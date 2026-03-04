from datetime import datetime, timezone

from fastapi.testclient import TestClient

from auth import Session, get_current_session
from main import app
from rate_limits import RATE_LIMIT_STORE


def _override_session(role: str = "admin", username: str = "sprint8"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def setup_function():
    RATE_LIMIT_STORE.reset()
    app.dependency_overrides = {}


def test_admin_runtime_rate_limit_config_contract_and_update_roundtrip():
    app.dependency_overrides[get_current_session] = _override_session("admin", "ops-admin")
    client = TestClient(app)

    snap = client.get("/admin/security/runtime-rate-limit-config")
    assert snap.status_code == 200
    body = snap.json()
    assert body["ok"] is True
    assert body["admin_editable"] is True
    assert "web_runtime" in body
    assert "rate_limit_ui" in body
    assert "defaultRetrySeconds" in body["rate_limit_ui"]
    assert "helperMessage" in body["rate_limit_ui"]

    original = body
    try:
        update = client.put(
            "/admin/security/runtime-rate-limit-config",
            json={
                "web_runtime": {
                    "required_node_min": "20.12.0",
                    "required_npm_major": 10,
                    "notes": "runtime policy updated for sprint-8 test",
                },
                "rate_limit_ui": {
                    "defaultRetrySeconds": 42,
                    "helperMessage": "Wait for cooldown, then retry.",
                },
            },
        )
        assert update.status_code == 200
        updated = update.json()
        assert updated["web_runtime"]["required_node_min"] == "20.12.0"
        assert updated["rate_limit_ui"]["default_retry_seconds"] == 42
        assert updated["rate_limit_ui"]["defaultRetrySeconds"] == 42
        assert updated["rate_limit_ui"]["helper_message"] == "Wait for cooldown, then retry."
        assert updated["rate_limit_ui"]["helperMessage"] == "Wait for cooldown, then retry."
    finally:
        client.put(
            "/admin/security/runtime-rate-limit-config",
            json={
                "web_runtime": original.get("web_runtime", {}),
                "rate_limit_ui": {
                    "default_retry_seconds": original.get("rate_limit_ui", {}).get("default_retry_seconds", 30),
                    "helper_message": original.get("rate_limit_ui", {}).get("helper_message", ""),
                },
            },
        )
