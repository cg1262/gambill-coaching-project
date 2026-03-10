from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from main import app


def _override_session(role: str = "editor", username: str = "coach1"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _base_intake(submission_id: str = "sub-1"):
    return {
        "submission_id": submission_id,
        "workspace_id": "ws-1",
        "applicant_name": "Candidate",
        "applicant_email": "candidate@example.com",
        "preferences_json": {},
        "job_links_json": [],
        "resume_text": "resume",
        "self_assessment_text": "assessment",
    }


def test_generate_sow_requires_active_subscription(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(main, "get_coaching_account_subscription", lambda workspace_id, username=None, email=None: None)

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
    )
    assert res.status_code == 403
    app.dependency_overrides = {}


def test_generate_sow_applies_guardrails_and_persists_run(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )

    def _bad_skeleton(intake, parsed_jobs):
        return {
            "schema_version": "0.2",
            "project_title": "x",
            "candidate_profile": {},
            "business_outcome": {},
            "solution_architecture": {"medallion_plan": {"bronze": "", "silver": "", "gold": ""}},
            "project_story": {},
            "milestones": [],
            "roi_dashboard_requirements": {},
            "resource_plan": {"required": [], "recommended": [], "optional": []},
            "mentoring_cta": {},
        }

    monkeypatch.setattr(main, "build_sow_skeleton", _bad_skeleton)

    captured = {}

    def _save_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(main, "save_coaching_generation_run", _save_run)

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert isinstance(body["auto_revised"], bool)
    assert body["schema"]["strict_enforced"] is True
    assert captured["validation"]["guardrails"]["strict_schema"] is True
    assert isinstance(body["sow"]["milestones"], list)
    assert body["sow"]["resource_plan"]["required"]
    assert body["quality"]["quality_diagnostics"]["floor_score"] == 80
    assert "auto_regenerated_for_quality_floor" in body["quality_flags"]
    assert "quality_diagnostics" in captured["validation"]["quality"]
    app.dependency_overrides = {}


def test_export_requires_active_subscription(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(main, "get_coaching_account_subscription", lambda workspace_id, username=None, email=None: {"subscription_status": "inactive"})

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/export",
        json={
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "format": "json",
            "sow": {
                "schema_version": "0.2",
                "project_title": "Demo",
                "candidate_profile": {},
                "business_outcome": {"problem_statement": "x"},
                "solution_architecture": {"medallion_plan": {"bronze": "a", "silver": "b", "gold": "c"}},
                "project_story": {"executive_summary": "x", "challenge": "y", "approach": "z", "impact_story": "q"},
                "milestones": [
                    {"name": "M1", "duration_weeks": 1, "deliverables": ["d1"], "milestone_tags": ["discovery"], "resources": [{"title": "r1", "url": "https://docs.python.org"}]},
                    {"name": "M2", "duration_weeks": 1, "deliverables": ["d2"], "milestone_tags": ["bronze"], "resources": [{"title": "r2", "url": "https://airflow.apache.org/docs/"}]},
                    {"name": "M3", "duration_weeks": 1, "deliverables": ["d3"], "milestone_tags": ["gold"], "resources": [{"title": "r3", "url": "https://learn.microsoft.com/power-bi/"}]},
                ],
                "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
                "resource_plan": {
                    "required": [{"title": "x", "url": "https://example.com"}],
                    "recommended": [],
                    "optional": [],
                    "affiliate_disclosure": "Some links may be affiliate links.",
                    "trust_language": "Recommendations are optional and unbiased.",
                },
                "mentoring_cta": {"recommended_tier": "Bi-weekly 1:1", "reason": "x", "trust_language": "optional"},
            },
        },
    )
    assert res.status_code == 403
    app.dependency_overrides = {}


def test_generate_sow_handles_malformed_llm_sections_without_500(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )

    def _malformed_llm(intake, parsed_jobs):
        sow = main.build_sow_skeleton(intake, parsed_jobs)
        sow["mentoring_cta"] = "Book a 1:1 call with token=abc123"
        sow["resource_plan"] = "not a dict"
        return {"ok": True, "sow": sow, "meta": {"provider": "openai-compatible", "model": "gpt-test"}}

    monkeypatch.setattr(main, "generate_sow_with_llm", _malformed_llm)

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
    )

    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert isinstance((body.get("sow") or {}).get("mentoring_cta"), dict)
    assert isinstance((body.get("sow") or {}).get("resource_plan"), dict)
    app.dependency_overrides = {}
