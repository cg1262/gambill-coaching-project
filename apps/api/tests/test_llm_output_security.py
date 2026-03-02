from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session, issue_token
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


def test_probabilistic_validation_reports_missing_llm_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    client = TestClient(app)
    res = client.post(
        "/validate/probabilistic",
        json={
            "version": "1.0",
            "workspace_id": "ws-1",
            "tables": [],
            "relationships": [],
            "modified_table_ids": [],
        },
        headers={"Authorization": "Bearer " + issue_token("editor-user", "editor")},
    )
    assert res.status_code == 200
    body = res.json()
    assert any(v["code"] == "LLM_API_KEY_MISSING" for v in body.get("violations", []))


def test_generated_sow_blocks_unsafe_urls_and_secret_text(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )

    def _unsafe_skeleton(intake, parsed_jobs):
        return {
            "schema_version": "0.2",
            "project_title": "x",
            "candidate_profile": {},
            "business_outcome": {"problem_statement": "ok"},
            "solution_architecture": {"medallion_plan": {"bronze": "b", "silver": "s", "gold": "g"}},
            "milestones": [
                {"name": "M1", "duration_weeks": 1, "deliverables": ["d1"], "milestone_tags": ["discovery"]},
                {"name": "M2", "duration_weeks": 1, "deliverables": ["d2"], "milestone_tags": ["bronze"]},
                {"name": "M3", "duration_weeks": 1, "deliverables": ["d3"], "milestone_tags": ["gold"]},
            ],
            "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
            "resource_plan": {
                "required": [{"title": "token=supersecret", "url": "javascript:alert(1)", "reason": "api_key=hunter2"}],
                "recommended": [],
                "optional": [],
                "affiliate_disclosure": "Bearer abc.def.ghi",
                "trust_language": "safe",
            },
            "mentoring_cta": {
                "recommended_tier": "core",
                "reason": "token=abc123",
                "trust_language": "ok",
                "program_url": "data:text/html,evil",
            },
        }

    monkeypatch.setattr(main, "build_sow_skeleton", _unsafe_skeleton)

    try:
        client = TestClient(app)
        res = client.post(
            "/coaching/sow/generate",
            json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
        )
        assert res.status_code == 200
        body = res.json()

        serialized = str(body).lower()
        assert "javascript:" not in serialized
        assert "data:text/html" not in serialized
        assert "supersecret" not in serialized
        assert "hunter2" not in serialized

        urls = []
        for bucket in ("required", "recommended", "optional"):
            for item in (body.get("sow", {}).get("resource_plan", {}).get(bucket, []) or []):
                if isinstance(item, dict) and item.get("url"):
                    urls.append(str(item.get("url")))
        program_url = str((body.get("sow", {}).get("mentoring_cta", {}) or {}).get("program_url") or "")
        if program_url:
            urls.append(program_url)
        assert all(u.startswith("http://") or u.startswith("https://") for u in urls)
    finally:
        app.dependency_overrides = {}
