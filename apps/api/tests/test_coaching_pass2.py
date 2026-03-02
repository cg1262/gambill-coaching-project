from datetime import datetime, timezone
from fastapi.testclient import TestClient

from auth import Session, get_current_session
from main import app


def _override_session(role: str = "editor"):
    def _inner():
        return Session(username="tester", role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_coaching_sow_validate_requires_structured_model(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr("main.get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "applicant_email": "candidate@example.com"})
    monkeypatch.setattr("main._require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})

    client = TestClient(app)
    payload = {
        "workspace_id": "ws-1",
        "submission_id": "sub-1",
        "sow": {
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
                {"name": "M1", "duration_weeks": 1, "deliverables": ["d1"], "milestone_tags": ["discovery"]},
                {"name": "M2", "duration_weeks": 1, "deliverables": ["d2"], "milestone_tags": ["bronze"]},
                {"name": "M3", "duration_weeks": 1, "deliverables": ["d3"], "milestone_tags": ["gold"]},
            ],
            "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
            "resource_plan": {
                "required": [{"title": "x", "url": "https://example.com"}],
                "recommended": [],
                "optional": [],
                "affiliate_disclosure": "Some links may be affiliate links.",
                "trust_language": "Recommendations are optional and unbiased.",
            },
            "mentoring_cta": {"recommended_tier": "Bi-weekly 1:1", "reason": "x", "trust_language": "Mentoring recommendation is optional.", "program_url": "https://example.org/program"},
        },
    }

    res = client.post("/coaching/sow/validate", json=payload)
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "valid" in res.json()
    app.dependency_overrides = {}


def test_coaching_seed_package_endpoint(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")
    monkeypatch.setattr("main.list_coaching_intake_submissions", lambda workspace_id, limit=1, review_status=None: [{"applicant_name": "Alex"}])

    client = TestClient(app)
    res = client.get("/coaching/demo/seed-package", params={"workspace_id": "ws-1"})
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "project_package" in body
    assert body["project_package"]["sow"]["resource_plan"]["required"]
    app.dependency_overrides = {}
