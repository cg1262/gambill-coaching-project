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


def test_subscription_sync_logging_masks_email_and_raw_event_token(monkeypatch):
    captured: list[dict] = []

    def _fake_logger(msg, *args, **kwargs):
        captured.append({"msg": msg, "kwargs": kwargs})

    monkeypatch.setattr(main.logger, "info", _fake_logger)
    monkeypatch.setattr(main, "save_coaching_subscription_event", lambda **kwargs: None)
    monkeypatch.setattr(main, "upsert_coaching_account_subscription", lambda **kwargs: None)

    client = TestClient(app)
    editor_token = issue_token("editor-user", "editor")
    res = client.post(
        "/coaching/subscription/sync",
        headers=_auth_header(editor_token),
        json={
            "workspace_id": "ws-1",
            "provider": "stripe",
            "event_type": "customer.subscription.updated",
            "email": "member@example.com",
            "plan_tier": "pro",
            "subscription_status": "active",
            "raw_event": {"authorization": "Bearer super-secret-token"},
        },
    )

    assert res.status_code == 200
    assert captured

    payload = captured[-1]["kwargs"]["extra"]["payload"]
    serialized = str(payload)
    assert "member@example.com" not in serialized
    assert "super-secret-token" not in serialized


def test_subscription_status_lookup_logging_masks_email(monkeypatch):
    captured: list[dict] = []

    def _fake_logger(msg, *args, **kwargs):
        captured.append({"msg": msg, "kwargs": kwargs})

    monkeypatch.setattr(main.logger, "info", _fake_logger)
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {
            "workspace_id": workspace_id,
            "username": username,
            "email": email,
            "plan_tier": "pro",
            "subscription_status": "active",
        },
    )

    client = TestClient(app)
    editor_token = issue_token("editor-user", "editor")
    res = client.get(
        "/coaching/subscription/status",
        headers=_auth_header(editor_token),
        params={"workspace_id": "ws-1", "email": "member@example.com"},
    )

    assert res.status_code == 200
    assert captured

    payload = captured[-1]["kwargs"]["extra"]["payload"]
    serialized = str(payload)
    assert "member@example.com" not in serialized
    assert payload["member_email_summary"]["pii_hits"]["email"] >= 1


def test_coaching_generate_denied_when_subscription_inactive(monkeypatch):
    client = TestClient(app)
    editor_token = issue_token("editor-user", "editor")

    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {
            "submission_id": submission_id,
            "applicant_name": "Test Candidate",
            "applicant_email": "member@example.com",
            "preferences_json": {},
            "resume_text": "resume",
            "self_assessment_text": "self",
            "job_links_json": [],
        },
    )
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {
            "workspace_id": workspace_id,
            "username": username,
            "email": email,
            "plan_tier": "pro",
            "subscription_status": "inactive",
        },
    )

    res = client.post(
        "/coaching/sow/generate",
        headers=_auth_header(editor_token),
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
    )
    assert res.status_code == 403



def test_coaching_generate_draft_denied_when_subscription_inactive(monkeypatch):
    client = TestClient(app)
    editor_token = issue_token("editor-user", "editor")

    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {
            "submission_id": submission_id,
            "applicant_name": "Test Candidate",
            "applicant_email": "member@example.com",
            "preferences_json": {},
            "resume_text": "resume",
            "self_assessment_text": "self",
            "job_links_json": [],
        },
    )
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {
            "workspace_id": workspace_id,
            "username": username,
            "email": email,
            "plan_tier": "pro",
            "subscription_status": "inactive",
        },
    )

    res = client.post(
        "/coaching/sow/generate-draft",
        headers=_auth_header(editor_token),
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
    )
    assert res.status_code == 403


def test_coaching_export_denied_when_subscription_inactive(monkeypatch):
    client = TestClient(app)
    editor_token = issue_token("editor-user", "editor")

    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {
            "submission_id": submission_id,
            "applicant_name": "Test Candidate",
            "applicant_email": "member@example.com",
            "preferences_json": {},
            "resume_text": "resume",
            "self_assessment_text": "self",
            "job_links_json": [],
        },
    )
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {
            "workspace_id": workspace_id,
            "username": username,
            "email": email,
            "plan_tier": "pro",
            "subscription_status": "inactive",
        },
    )

    res = client.post(
        "/coaching/sow/export",
        headers=_auth_header(editor_token),
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "format": "markdown",
            "sow": {
                "project_title": "p",
                "business_outcome": {"problem_statement": "x", "kpi_targets": ["k"], "roi_hypothesis": "r"},
                "solution_architecture": {"medallion_plan": {"bronze": "b", "silver": "s", "gold": "g"}, "orchestration": ["o"], "semantic_model_outline": ["m"]},
                "project_story": {"business_narrative": "n", "interview_highlights": ["h1"]},
                "milestones": [{"name": "m1", "duration_weeks": 1, "deliverables": ["d"]}, {"name": "m2", "duration_weeks": 1, "deliverables": ["d"]}, {"name": "m3", "duration_weeks": 1, "deliverables": ["d"]}],
                "roi_dashboard_requirements": {"required_measures": ["m"], "required_dimensions": ["d"], "target_visuals": ["v"]},
                "resource_plan": {
                    "required": [{"title": "t", "url": "https://example.com", "type": "article", "reason": "r"}],
                    "recommended": [],
                    "optional": [],
                },
                "mentoring_cta": {"recommended_tier": "pro", "reason": "r", "offer": "o", "pricing": "p", "timeline": "t", "cta_text": "c"},
            },
        },
    )
    assert res.status_code == 403


def test_coaching_intake_rejects_unsafe_job_link_scheme():
    client = TestClient(app)
    editor_token = issue_token("admin-user", "admin")

    payload = {
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "resume_text": "Resume text",
        "self_assessment_text": "Self assessment",
        "job_links": ["javascript:alert(1)"],
        "preferences": {"timeline_weeks": 8},
    }

    res = client.post("/coaching/intake", json=payload, headers=_auth_header(editor_token))
    assert res.status_code == 422


def test_coaching_intake_rejects_malformed_job_links_payload():
    client = TestClient(app)
    editor_token = issue_token("admin-user", "admin")

    payload = {
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "resume_text": "Resume text",
        "self_assessment_text": "Self assessment",
        "job_links": [{"href": "https://example.com/job/1"}],
        "preferences": {"timeline_weeks": 8},
    }

    res = client.post("/coaching/intake", json=payload, headers=_auth_header(editor_token))
    assert res.status_code == 422


def test_coaching_intake_rejects_excessively_long_freeform_fields():
    client = TestClient(app)
    editor_token = issue_token("admin-user", "admin")

    payload = {
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "resume_text": "R" * 12001,
        "self_assessment_text": "S" * 12001,
        "job_links": ["https://example.com/job/1"],
        "preferences": {"timeline_weeks": 8},
    }

    res = client.post("/coaching/intake", json=payload, headers=_auth_header(editor_token))
    assert res.status_code == 422


def test_subscription_denial_response_is_generic(monkeypatch):
    client = TestClient(app)
    viewer_token = issue_token("viewer-user", "viewer")

    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {
            "workspace_id": workspace_id,
            "username": username,
            "email": email,
            "plan_tier": "pro",
            "subscription_status": "inactive",
        },
    )

    res = client.get(
        "/coaching/intake/submissions",
        params={"workspace_id": "ws-1"},
        headers=_auth_header(viewer_token),
    )
    assert res.status_code == 403
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "subscription_required"
    assert body["auth_required"] is False
    assert body["subscription_required"] is True
    assert "inactive" not in str(body).lower()
