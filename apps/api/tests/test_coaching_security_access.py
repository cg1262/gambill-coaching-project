from fastapi.testclient import TestClient

import main
from main import app
from auth import issue_token


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_coaching_intake_requires_valid_bearer_token():
    client = TestClient(app)
    payload = {
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "applicant_email": "candidate@example.com",
        "resume_text": "Resume text",
        "self_assessment_text": "Self assessment",
        "job_links": ["https://example.com/job/1"],
        "preferences": {"timeline_weeks": 8},
    }

    missing = client.post("/coaching/intake", json=payload)
    assert missing.status_code == 401

    malformed = client.post("/coaching/intake", json=payload, headers={"Authorization": "Token abc123"})
    assert malformed.status_code == 401


def test_coaching_intake_blocks_reused_or_invalidated_token():
    client = TestClient(app)
    token = issue_token("editor-user", "editor")

    logout_res = client.post("/auth/logout", headers=_auth_header(token))
    assert logout_res.status_code == 200

    payload = {
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "applicant_email": "candidate@example.com",
        "resume_text": "Resume text",
        "self_assessment_text": "Self assessment",
        "job_links": ["https://example.com/job/1"],
        "preferences": {"timeline_weeks": 8},
    }
    reused = client.post("/coaching/intake", json=payload, headers=_auth_header(token))
    assert reused.status_code == 401


def test_coaching_subscription_status_denies_viewer_role():
    client = TestClient(app)
    viewer_token = issue_token("viewer-user", "viewer")
    res = client.post(
        "/coaching/subscription/status",
        headers=_auth_header(viewer_token),
        json={
            "workspace_id": "ws-1",
            "member_email": "member@example.com",
            "subscription_status": "active",
            "plan_tier": "pro",
            "launch_token": "launch-secret-token",
        },
    )
    assert res.status_code == 403


def test_subscription_status_logging_masks_email_and_token(monkeypatch):
    captured: list[dict] = []

    def _fake_logger(msg, *args, **kwargs):
        captured.append({"msg": msg, "kwargs": kwargs})

    monkeypatch.setattr(main.logger, "info", _fake_logger)

    client = TestClient(app)
    editor_token = issue_token("editor-user", "editor")
    res = client.post(
        "/coaching/subscription/status",
        headers=_auth_header(editor_token),
        json={
            "workspace_id": "ws-1",
            "member_email": "member@example.com",
            "subscription_status": "active",
            "plan_tier": "pro",
            "launch_token": "launch-secret-token",
        },
    )

    assert res.status_code == 200
    assert captured, "Expected structured security log entry"

    payload = captured[-1]["kwargs"]["extra"]["payload"]
    serialized = str(payload)
    assert "member@example.com" not in serialized
    assert "launch-secret-token" not in serialized
    assert payload["member_email_summary"]["pii_hits"]["email"] >= 1
    assert payload["launch_token_summary"]["length"] > 0


def test_auth_login_logging_never_includes_password(monkeypatch):
    captured: list[dict] = []

    def _fake_logger(msg, *args, **kwargs):
        captured.append({"msg": msg, "kwargs": kwargs})

    monkeypatch.setattr(main.logger, "info", _fake_logger)

    client = TestClient(app)
    res = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200
    assert captured

    serialized = str(captured[-1])
    assert "admin123" not in serialized
