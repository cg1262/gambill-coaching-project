from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "editor", username: str = "coach1"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _active_subscription(*args, **kwargs):
    return {"subscription_status": "active", "plan_tier": "pro", "email": kwargs.get("email")}


def _inactive_subscription(*args, **kwargs):
    return {"subscription_status": "inactive", "plan_tier": "starter", "email": kwargs.get("email")}


def _base_intake(submission_id: str = "sub-1"):
    return {
        "submission_id": submission_id,
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "applicant_email": "candidate@example.com",
        "preferences_json": {},
        "job_links_json": ["https://example.org/jobs/1"],
        "resume_text": "resume",
        "self_assessment_text": "assessment",
    }


def _valid_sow_payload():
    return {
        "schema_version": "0.2",
        "project_title": "Demo",
        "candidate_profile": {},
        "business_outcome": {
            "problem_statement": "x",
            "target_metrics": [{"metric": "m", "target": "t"}],
            "domain_focus": ["retail"],
            "data_sources": [{"name": "n", "url": "https://data.city.gov", "ingestion_doc_url": "https://docs.city.gov/ingest"}],
        },
        "solution_architecture": {"medallion_plan": {"bronze": "a", "silver": "b", "gold": "c"}},
        "project_story": {"executive_summary": "x", "challenge": "y", "approach": "z", "impact_story": "q"},
        "milestones": [
            {"name": "M1", "duration_weeks": 1, "deliverables": ["d1"], "milestone_tags": ["discovery"], "resources": [{"title": "r1", "url": "https://docs.python.org"}]},
            {"name": "M2", "duration_weeks": 1, "deliverables": ["d2"], "milestone_tags": ["bronze"], "resources": [{"title": "r2", "url": "https://airflow.apache.org/docs/"}]},
            {"name": "M3", "duration_weeks": 1, "deliverables": ["d3"], "milestone_tags": ["gold"], "resources": [{"title": "r3", "url": "https://learn.microsoft.com/power-bi/"}]},
        ],
        "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
        "resource_plan": {
            "required": [{"title": "x", "url": "https://choosealicense.com/"}],
            "recommended": [],
            "optional": [],
            "affiliate_disclosure": "Some links may be affiliate links.",
            "trust_language": "Recommendations are optional and unbiased.",
        },
        "mentoring_cta": {"recommended_tier": "Bi-weekly 1:1", "reason": "x", "trust_language": "optional", "program_url": "https://example.org/program"},
    }


def test_a2_security_regression_flow_intake_generate_validate_export(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_account_subscription", _active_subscription)

    saved = {}
    monkeypatch.setattr(main, "save_coaching_intake_submission", lambda **kwargs: saved.update(kwargs))
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))

    client = TestClient(app)

    intake_res = client.post(
        "/coaching/intake",
        json={
            "workspace_id": "ws-1",
            "applicant_name": "Candidate",
            "applicant_email": "candidate@example.com",
            "resume_text": "resume text",
            "self_assessment_text": "assessment",
            "job_links": ["https://example.org/jobs/1"],
            "preferences": {},
        },
    )
    assert intake_res.status_code == 200
    submission_id = intake_res.json()["submission_id"]
    assert saved["submission_id"] == submission_id

    monkeypatch.setattr(main, "generate_sow_with_llm", lambda intake, parsed_jobs: {"ok": True, "sow": _valid_sow_payload(), "meta": {"provider": "openai-compatible"}})
    gen_res = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": submission_id, "parsed_jobs": []})
    assert gen_res.status_code == 200
    sow = gen_res.json()["sow"]

    val_res = client.post("/coaching/sow/validate", json={"workspace_id": "ws-1", "submission_id": submission_id, "sow": sow})
    assert val_res.status_code == 200
    assert val_res.json()["ok"] is True

    export_res = client.post("/coaching/sow/export", json={"workspace_id": "ws-1", "submission_id": submission_id, "format": "json", "sow": sow})
    assert export_res.status_code == 200
    assert export_res.json()["format"] == "json"

    app.dependency_overrides = {}


def test_c1_premium_review_endpoints_require_active_subscription(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "viewer1")
    monkeypatch.setattr(main, "get_coaching_account_subscription", _inactive_subscription)

    client = TestClient(app)
    open_res = client.get("/coaching/review/open-submissions", params={"workspace_id": "ws-1"})
    assert open_res.status_code == 403

    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    run_res = client.get("/coaching/review/submissions/sub-1/runs")
    assert run_res.status_code == 403

    detail_res = client.get("/coaching/intake/submissions/sub-1")
    assert detail_res.status_code == 403

    app.dependency_overrides = {}


def test_coach_review_status_update_forbids_viewer_role(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "viewer1")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(main, "get_coaching_account_subscription", _active_subscription)

    called = {"updated": False}
    monkeypatch.setattr(
        main,
        "update_coaching_review_status",
        lambda submission_id, coach_review_status, coach_notes: called.update(updated=True),
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/review/status",
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "coach_review_status": "in_review",
            "coach_notes": "looks good",
        },
    )
    assert res.status_code == 403
    assert called["updated"] is False

    app.dependency_overrides = {}


def test_coach_review_status_update_requires_active_subscription(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach2")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(main, "get_coaching_account_subscription", _inactive_subscription)

    called = {"updated": False}
    monkeypatch.setattr(
        main,
        "update_coaching_review_status",
        lambda submission_id, coach_review_status, coach_notes: called.update(updated=True),
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/review/status",
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "coach_review_status": "in_review",
            "coach_notes": "needs rewrite",
        },
    )
    assert res.status_code == 403
    assert called["updated"] is False

    app.dependency_overrides = {}


def test_e1_llm_readiness_endpoint(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "ops")

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    monkeypatch.setattr(main, "_check_llm_provider_reachability", lambda base_url, api_key, timeout_sec=4: (True, "HTTP 200"))

    client = TestClient(app)
    res = client.get("/coaching/health/llm-readiness")
    assert res.status_code == 200
    body = res.json()
    assert body["readiness"]["api_key_present"] is True
    assert body["readiness"]["provider_reachable"] is True
    assert body["readiness"]["ready"] is True

    app.dependency_overrides = {}


def test_e2_fetch_job_text_blocks_unsafe_urls():
    from coaching import fetch_job_text

    blocked_file = fetch_job_text("file:///etc/passwd")
    assert blocked_file["ok"] is False
    assert "Unsafe URL blocked" in blocked_file["error"]

    blocked_localhost = fetch_job_text("http://localhost/internal")
    assert blocked_localhost["ok"] is False
    assert "Unsafe URL blocked" in blocked_localhost["error"]


def test_c1_premium_validate_loop_requires_active_subscription(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach1")
    monkeypatch.setattr(main, "get_coaching_account_subscription", _inactive_subscription)
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/validate-loop",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "sow": _valid_sow_payload(), "auto_revise_once": True},
    )
    assert res.status_code == 403
    app.dependency_overrides = {}


def test_d1_intake_submissions_filter_passed_to_storage(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "coach1")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    captured = {}

    def _list(workspace_id, limit=50, review_status=None):
        captured["workspace_id"] = workspace_id
        captured["limit"] = limit
        captured["review_status"] = review_status
        return [{"submission_id": "sub-1", "coach_review_status": review_status or "new"}]

    monkeypatch.setattr(main, "list_coaching_intake_submissions", _list)

    client = TestClient(app)
    res = client.get("/coaching/intake/submissions", params={"workspace_id": "ws-1", "status": "in_review", "limit": 10})
    assert res.status_code == 200
    assert captured["review_status"] == "in_review"
    assert res.json()["status_filter"] == "in_review"
    app.dependency_overrides = {}
