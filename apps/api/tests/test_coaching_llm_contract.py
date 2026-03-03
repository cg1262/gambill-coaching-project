from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching import validate_sow_payload
from main import app


def _override_session(role: str = "editor", username: str = "coach1"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _base_intake(submission_id: str = "sub-llm"):
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


def test_validator_flags_required_contract_fields():
    sow = {
        "project_title": "Bad",
        "business_outcome": {"data_sources": [{"name": "x", "url": "https://example.com", "ingestion_doc_url": ""}]},
        "solution_architecture": {"medallion_plan": {"bronze": "", "silver": "", "gold": ""}},
        "milestones": [
            {"name": "m1", "duration_weeks": 1, "deliverables": [], "milestone_tags": []},
            {"name": "m2", "duration_weeks": 1, "deliverables": [], "milestone_tags": []},
            {"name": "m3", "duration_weeks": 1, "deliverables": [], "milestone_tags": []},
        ],
        "roi_dashboard_requirements": {},
        "resource_plan": {"required": [], "recommended": [], "optional": []},
        "mentoring_cta": {},
    }
    codes = {f["code"] for f in validate_sow_payload(sow)}
    assert "PROJECT_STORY_MISSING" in codes
    assert "INGESTION_DOC_LINK_MISSING" in codes
    assert "MILESTONE_RESOURCES_MISSING" in codes


def test_generate_sow_uses_llm_meta_and_quality_flags(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )

    monkeypatch.setattr(
        main,
        "generate_sow_with_llm",
        lambda intake, parsed_jobs: {
            "ok": True,
            "sow": {
                "schema_version": "0.2",
                "project_title": "LLM draft",
                "candidate_profile": {},
                "business_outcome": {"problem_statement": "x", "target_metrics": [], "domain_focus": [], "data_sources": []},
                "solution_architecture": {"medallion_plan": {"bronze": "", "silver": "", "gold": ""}},
                "project_story": {},
                "milestones": [],
                "roi_dashboard_requirements": {},
                "resource_plan": {"required": [], "recommended": [], "optional": []},
                "mentoring_cta": {},
            },
            "meta": {"provider": "openai-compatible", "model": "gpt-test"},
        },
    )

    captured = {}
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: captured.update(kwargs))

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": "sub-llm", "parsed_jobs": []},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["quality_flags"]["used_llm_provider"] is True
    assert body["quality_flags"]["retried_after_validation"] is True
    assert body["generation_meta"]["model"] == "gpt-test"
    assert body["sow"]["project_story"]["executive_summary"]
    assert body["sow"]["milestones"][0]["resources"]
    assert body["sow"]["milestones"][0]["execution_plan"]
    assert body["sow"]["milestones"][0]["expected_deliverable"]
    assert body["sow"]["milestones"][0]["business_why"]
    assert body["quality"]["quality_diagnostics"]["floor_score"] == 80
    assert captured["validation"]["generation_meta"]["provider"] == "openai-compatible"
    assert "quality_flags" in captured["validation"]

    app.dependency_overrides = {}
