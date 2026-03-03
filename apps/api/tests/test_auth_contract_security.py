from fastapi.testclient import TestClient
import pytest

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


@pytest.mark.parametrize(
    "method,path,payload",
    [
        ("GET", "/coaching/health/readiness", {"workspace_id": "ws-1"}),
        ("POST", "/coaching/sow/generate-draft", {"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []}),
        ("GET", "/coaching/intake/submissions", {"workspace_id": "ws-1"}),
    ],
)
def test_coaching_401_payload_is_generic_on_protected_routes(method, path, payload):
    client = TestClient(app)
    if method == "GET":
        res = client.get(path, params=payload)
    else:
        res = client.post(path, json=payload)
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "auth_required"
    assert body["auth_required"] is True
    assert body["subscription_required"] is False
    assert "Missing bearer token" not in str(body)
    assert "Invalid or expired token" not in str(body)


def test_coaching_403_payload_is_generic_for_role_denial(monkeypatch):
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )
    client = TestClient(app)
    viewer = issue_token("viewer-user", "viewer")
    res = client.post(
        "/coaching/jobs/parse",
        json={"workspace_id": "ws-1", "submission_id": "sub-1"},
        headers=_auth_header(viewer),
    )
    assert res.status_code == 403
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "forbidden"
    assert body["auth_required"] is False
    assert body["subscription_required"] is False
    assert "invalid or expired token" not in str(body).lower()


def test_coaching_403_payload_is_generic_for_subscription_denial(monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setattr(
        main,
        "_require_active_coaching_subscription",
        lambda **kwargs: (_ for _ in ()).throw(HTTPException(status_code=403, detail="Active coaching subscription required")),
    )

    client = TestClient(app)
    viewer = issue_token("viewer-user", "viewer")
    res = client.get("/coaching/intake/submissions", params={"workspace_id": "ws-1"}, headers=_auth_header(viewer))
    assert res.status_code == 403
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "subscription_required"
    assert body["auth_required"] is False
    assert body["subscription_required"] is True
    assert "inactive" not in str(body).lower()


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
