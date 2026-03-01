from datetime import datetime, timezone
import pytest
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


@pytest.mark.parametrize("role,status_code", [("viewer", 403), ("editor", 200), ("admin", 200)])
def test_coaching_intake_rbac(role, status_code, monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session(role)
    monkeypatch.setattr(main, "save_coaching_intake_submission", lambda **kwargs: None)

    client = TestClient(app)
    res = client.post(
        "/coaching/intake",
        json={
            "workspace_id": "ws-1",
            "applicant_name": "Test Candidate",
            "applicant_email": "candidate@example.com",
            "resume_text": "Experienced in Spark",
            "self_assessment_text": "Need depth in orchestration",
            "job_links": ["https://example.com/job/1"],
            "preferences": {"timeline_weeks": 6},
        },
    )
    assert res.status_code == status_code
    app.dependency_overrides = {}


@pytest.mark.parametrize("role,status_code", [("viewer", 403), ("editor", 200), ("admin", 200)])
def test_coaching_jobs_parse_rbac(role, status_code, monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session(role)
    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {"submission_id": submission_id, "job_links_json": []},
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/jobs/parse",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "force_refresh": False},
    )
    assert res.status_code == status_code
    app.dependency_overrides = {}


@pytest.mark.parametrize("role,status_code", [("viewer", 403), ("editor", 200), ("admin", 200)])
def test_coaching_generate_sow_rbac(role, status_code, monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session(role)
    monkeypatch.setattr(
        main,
        "get_coaching_intake_submission",
        lambda submission_id: {
            "submission_id": submission_id,
            "applicant_name": "Test Candidate",
            "preferences_json": {},
            "applicant_email": "candidate@example.com",
            "resume_text": "resume",
            "self_assessment_text": "self",
            "job_links_json": ["https://example.com/job/1"],
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
            "subscription_status": "active",
        },
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "parsed_jobs": [{"url": "https://example.com/job/1", "signals": {"skills": ["python"]}}],
        },
    )
    assert res.status_code == status_code
    app.dependency_overrides = {}

@pytest.mark.parametrize("role,status_code", [("viewer", 403), ("editor", 200), ("admin", 200)])
def test_coaching_validate_loop_rbac(role, status_code, monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session(role)
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id})
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/validate-loop",
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "sow": {
                "project_title": "p",
                "business_outcome": {},
                "solution_architecture": {"medallion_plan": {"bronze": "x", "silver": "y", "gold": "z"}},
                "milestones": [{"name": "m1"}, {"name": "m2"}, {"name": "m3"}],
                "roi_dashboard_requirements": {"required_measures": ["m"], "required_dimensions": ["d"]},
                "resource_plan": {"required": [{"url": "https://example.com"}], "recommended": [], "optional": []},
                "mentoring_cta": {"recommended_tier": "TBD", "reason": "x"},
            },
            "auto_revise_once": False,
        },
    )
    assert res.status_code == status_code
    app.dependency_overrides = {}
