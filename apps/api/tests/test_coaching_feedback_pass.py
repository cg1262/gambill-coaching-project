from datetime import datetime, timezone
from fastapi.testclient import TestClient

import main
from main import app
from auth import Session, issue_token, get_current_session


def _override_session(role: str = "editor"):
    def _inner():
        return Session(username=f"{role}-user", role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _payload() -> dict:
    return {
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "applicant_email": "candidate@example.com",
        "resume_text": "Resume text",
        "self_assessment_text": "Self assessment",
        "job_links": ["https://example.org/job/1"],
        "preferences": {"timeline_weeks": 8},
    }


def test_intake_401_returns_guidance_payload():
    client = TestClient(app)
    res = client.post("/coaching/intake", json=_payload())
    assert res.status_code == 401
    body = res.json()
    assert body["code"] == "auth_required"
    assert body["auth_required"] is True
    assert "message" in body


def test_readiness_403_returns_subscription_guidance(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")

    # force helper to emit HTTPException with subscription detail
    def _raise_sub(**kwargs):
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail={"code": "subscription_required", "subscription_required": True, "message": "Active coaching subscription required."})

    monkeypatch.setattr(main, "_require_active_coaching_subscription", _raise_sub)

    client = TestClient(app)
    res = client.get("/coaching/health/readiness", params={"workspace_id": "ws-1"})
    assert res.status_code == 403
    body = res.json()
    assert body["code"] == "subscription_required"
    assert body["subscription_required"] is True

    app.dependency_overrides.clear()


def test_intake_rejects_invalid_structured_job_link():
    client = TestClient(app)
    token = issue_token("editor-user", "editor")
    payload = _payload()
    payload["job_links"] = [{"url": "not-a-url", "title": "bad"}]
    res = client.post("/coaching/intake", json=payload, headers=_auth_header(token))
    assert res.status_code == 422
    assert "job_links[0].url" in str(res.json())


def test_intake_persists_self_assessment_and_stack_tool_arrays(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})

    saved = {}
    monkeypatch.setattr(main, "save_coaching_intake_submission", lambda **kwargs: saved.update(kwargs))

    client = TestClient(app)
    payload = _payload()
    payload["job_links"] = [{"url": "https://example.org/job/1", "title": "DE role", "source": "linkedin"}]
    payload["self_assessment"] = {"sql_confidence": "high", "interview_readiness": "medium"}
    payload["stack_preferences"] = ["python", "sql"]
    payload["tool_preferences"] = ["dbt", "airflow"]

    res = client.post("/coaching/intake", json=payload)
    assert res.status_code == 200
    assert saved["job_links"] == ["https://example.org/job/1"]
    assert saved["preferences"]["self_assessment"]["sql_confidence"] == "high"
    assert saved["preferences"]["stack_preferences"] == ["python", "sql"]
    assert saved["preferences"]["tool_preferences"] == ["dbt", "airflow"]

    app.dependency_overrides.clear()


def test_recommendations_endpoint_returns_top_stack_and_tools(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")

    monkeypatch.setattr(main, "fetch_job_text", lambda url: {"ok": True, "text": f"Need python sql dbt on {url}", "error": None})
    monkeypatch.setattr(main, "extract_job_signals", lambda text: {"skills": ["python", "sql"], "tools": ["dbt", "airflow"]})

    client = TestClient(app)
    res = client.post(
        "/coaching/jobs/recommendations",
        json={
            "workspace_id": "ws-1",
            "job_links": ["https://example.org/job/1", {"url": "https://example.org/job/2"}],
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["recommendations"]["stack"][0]["name"] in {"python", "sql"}
    assert body["recommendations"]["tools"][0]["name"] in {"dbt", "airflow"}

    app.dependency_overrides.clear()
