from datetime import datetime, timezone
from fastapi.testclient import TestClient

import main
from main import app
from auth import Session, get_current_session, get_current_user


def _override_session(role: str):
    def _inner():
        return Session(username="tester", role=role, expires_at=datetime.now(timezone.utc))
    return _inner


def test_admin_users_forbidden_for_editor():
    app.dependency_overrides[get_current_session] = _override_session("editor")
    client = TestClient(app)
    res = client.get("/admin/users")
    assert res.status_code == 403
    app.dependency_overrides = {}


def test_admin_users_allowed_for_admin(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("admin")
    monkeypatch.setattr(main, "list_users", lambda: [{"username": "admin", "role": "admin", "active": True}])
    client = TestClient(app)
    res = client.get("/admin/users")
    assert res.status_code == 200
    app.dependency_overrides = {}


def test_runs_history_requires_user_auth(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: "tester"
    monkeypatch.setattr(main, "get_run_history", lambda workspace_id, limit=50: [{"id": "1", "run_type": "impact", "pass_type": "deterministic", "actor_user": "tester", "run_at": "2026-01-01T00:00:00Z"}])
    client = TestClient(app)
    res = client.get("/runs/history", params={"workspace_id": "ws-1"})
    assert res.status_code == 200
    app.dependency_overrides = {}
