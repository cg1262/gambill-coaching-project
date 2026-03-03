from fastapi.testclient import TestClient

import main
from main import app
from auth import issue_token


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_auth_401_payload_is_generic_for_auth_routes():
    client = TestClient(app)
    res = client.post("/auth/refresh")
    assert res.status_code == 401
    body = res.json()
    assert body["code"] == "auth_required"
    assert body["auth_required"] is True
    assert "Missing bearer token" not in str(body)
    assert "Invalid or expired token" not in str(body)


def test_401_then_success_response_does_not_preserve_auth_error_flags(monkeypatch):
    monkeypatch.setattr(main, "fetch_job_text", lambda url: {"ok": True, "text": "Need python and dbt", "error": None})
    monkeypatch.setattr(main, "extract_job_signals", lambda text: {"skills": ["python"], "tools": ["dbt"]})

    client = TestClient(app)

    unauth = client.post(
        "/coaching/jobs/recommendations",
        json={"workspace_id": "ws-1", "job_links": ["https://example.org/job/1"]},
        headers={"Authorization": "Bearer invalid-token"},
    )
    assert unauth.status_code == 401
    unauth_body = unauth.json()
    assert unauth_body["auth_required"] is True

    token = issue_token("editor-user", "editor")
    ok = client.post(
        "/coaching/jobs/recommendations",
        json={"workspace_id": "ws-1", "job_links": ["https://example.org/job/1"]},
        headers=_auth_header(token),
    )
    assert ok.status_code == 200
    body = ok.json()
    assert body["ok"] is True
    assert "auth_required" not in body
    assert "subscription_required" not in body
    assert "code" not in body
