from datetime import datetime, timezone

from fastapi.testclient import TestClient
import pytest

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


def test_regenerate_quality_delta_response_does_not_leak_prior_sensitive_payload(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)

    monkeypatch.setattr(
        main,
        "list_coaching_generation_runs",
        lambda submission_id, limit=1: [
            {
                "run_id": "old-run",
                "validation_json": {
                    "quality": {"score": 40},
                    "raw_provider_payload": {"api_key": "sk-super-secret", "token": "tok_private"},
                },
            }
        ],
    )

    monkeypatch.setattr(
        main,
        "generate_sow_with_llm",
        lambda intake, parsed_jobs: {"ok": True, "sow": main.build_sow_skeleton(intake, parsed_jobs), "meta": {"provider": "openai-compatible"}},
    )

    try:
        client = TestClient(app)
        res = client.post(
            "/coaching/sow/generate",
            json={
                "workspace_id": "ws-1",
                "submission_id": "sub-1",
                "parsed_jobs": [],
                "regenerate_with_improvements": True,
            },
        )
        assert res.status_code == 200
        body = res.json()
        assert body["quality"]["quality_delta"] is not None

        serialized = str(body).lower()
        assert "sk-super-secret" not in serialized
        assert "tok_private" not in serialized
        assert "raw_provider_payload" not in serialized
        assert "api_key" not in serialized
    finally:
        app.dependency_overrides = {}


def test_generation_meta_is_sanitized_and_secret_free(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )

    captured = {}
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: captured.update(kwargs))
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(
        main,
        "generate_sow_with_llm",
        lambda intake, parsed_jobs: {
            "ok": True,
            "sow": main.build_sow_skeleton(intake, parsed_jobs),
            "meta": {
                "provider": "openai-compatible",
                "model": "gpt-test",
                "attempts": 2,
                "finish_reason": "stop",
                "usage": {"prompt_tokens": 12, "completion_tokens": 34, "total_tokens": 46, "raw": "nope"},
                "base_url": "https://provider.example/v1",
                "api_key": "sk-super-secret",
                "raw_provider_payload": {"Authorization": "Bearer should-not-leak"},
            },
        },
    )

    try:
        client = TestClient(app)
        res = client.post(
            "/coaching/sow/generate",
            json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
        )
        assert res.status_code == 200
        body = res.json()

        meta = body.get("generation_meta") or {}
        assert meta["provider"] == "openai-compatible"
        assert meta["model"] == "gpt-test"
        assert meta["attempts"] == 2
        assert meta["usage"]["total_tokens"] == 46
        assert "base_url" not in meta
        assert "api_key" not in meta
        assert "raw_provider_payload" not in meta

        persisted_meta = ((captured.get("validation") or {}).get("generation_meta") or {})
        assert persisted_meta == meta

        serialized = str(body).lower()
        assert "sk-super-secret" not in serialized
        assert "should-not-leak" not in serialized
        assert "raw_provider_payload" not in serialized
    finally:
        app.dependency_overrides = {}


@pytest.mark.parametrize(
    "unsafe_url",
    [
        "http://127.0.0.1/private",
        "https://user:pass@localhost/admin",
        "https://internal.dev.local/admin",
        "data:text/html,evil",
        "javascript:alert(1)",
        "file:///etc/passwd",
    ],
)
def test_generated_sow_blocks_unsafe_urls_and_secret_text(monkeypatch, unsafe_url):
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
            "project_title": "x api_key=title-secret",
            "project_story": "project story bearer aaaa.bbbb.cccc",
            "candidate_profile": {},
            "business_outcome": {"problem_statement": "ok token=problem-secret"},
            "solution_architecture": {"medallion_plan": {"bronze": "b", "silver": "s", "gold": "g"}},
            "milestones": [
                {
                    "name": "M1 token=ms1",
                    "duration_weeks": 1,
                    "deliverables": ["d1", "api_key=deliverable-secret"],
                    "milestone_tags": ["discovery"],
                    "execution_plan": "execute with token=plan-secret",
                    "expected_deliverable": "deliver with password=hunter2",
                    "business_why": "why bearer aaa.bbb.ccc",
                },
                {"name": "M2", "duration_weeks": 1, "deliverables": ["d2"], "milestone_tags": ["bronze"]},
                {"name": "M3", "duration_weeks": 1, "deliverables": ["d3"], "milestone_tags": ["gold"]},
            ],
            "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
            "resource_plan": {
                "required": [{"title": "token=supersecret", "url": unsafe_url, "reason": "api_key=hunter2"}],
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
        assert unsafe_url.lower() not in serialized
        assert "data:text/html" not in serialized
        assert "supersecret" not in serialized
        assert "hunter2" not in serialized
        assert "title-secret" not in serialized
        assert "problem-secret" not in serialized
        assert "plan-secret" not in serialized
        assert "deliverable-secret" not in serialized

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

def test_project_story_narrative_fields_are_secret_masked(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )

    monkeypatch.setattr(
        main,
        "build_sow_skeleton",
        lambda intake, parsed_jobs: {
            "schema_version": "0.2",
            "project_title": "Title api_key=title-secret",
            "candidate_profile": {},
            "business_outcome": {"problem_statement": "safe", "data_sources": [{"name": "Public", "url": "https://example.org/data", "ingestion_doc_url": "https://example.org/docs", "selection_rationale": "safe"}]},
            "solution_architecture": {"medallion_plan": {"bronze": "b", "silver": "s", "gold": "g"}},
            "project_story": {
                "executive_summary": "token=story-secret",
                "challenge": "bearer aaa.bbb.ccc",
                "approach": "password=hunter2",
                "impact_story": "clean",
            },
            "milestones": [
                {"name": "M1", "duration_weeks": 1, "deliverables": ["d1"], "milestone_tags": ["discovery"], "resources": [{"title": "r", "url": "https://example.org/r1"}]},
                {"name": "M2", "duration_weeks": 1, "deliverables": ["d2"], "milestone_tags": ["bronze"], "resources": [{"title": "r", "url": "https://example.org/r2"}]},
                {"name": "M3", "duration_weeks": 1, "deliverables": ["d3"], "milestone_tags": ["gold"], "resources": [{"title": "r", "url": "https://example.org/r3"}]},
            ],
            "roi_dashboard_requirements": {"required_dimensions": ["time"], "required_measures": ["cost_savings"]},
            "resource_plan": {"required": [{"title": "r", "url": "https://example.org/res"}], "recommended": [], "optional": [], "affiliate_disclosure": "safe", "trust_language": "safe"},
            "mentoring_cta": {"trust_language": "safe", "program_url": "https://example.org/program"},
        },
    )

    try:
        client = TestClient(app)
        res = client.post(
            "/coaching/sow/generate",
            json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
        )
        assert res.status_code == 200
        serialized = str(res.json()).lower()
        assert "story-secret" not in serialized
        assert "hunter2" not in serialized
        assert "aaa.bbb.ccc" not in serialized
    finally:
        app.dependency_overrides = {}


def test_quality_diagnostics_remain_provider_secret_free(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_intake(submission_id))
    monkeypatch.setattr(
        main,
        "get_coaching_account_subscription",
        lambda workspace_id, username=None, email=None: {"subscription_status": "active", "email": email},
    )
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(
        main,
        "generate_sow_with_llm",
        lambda intake, parsed_jobs: {
            "ok": True,
            "sow": main.build_sow_skeleton(intake, parsed_jobs),
            "meta": {
                "provider": "openai-compatible",
                "model": "gpt-test",
                "attempts": 1,
                "api_key": "sk-super-secret",
                "base_url": "https://provider.example/v1",
                "raw_provider_payload": {"token": "tok-secret"},
            },
        },
    )

    try:
        client = TestClient(app)
        res = client.post(
            "/coaching/sow/generate",
            json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []},
        )
        assert res.status_code == 200
        diagnostics = (res.json().get("quality") or {}).get("quality_diagnostics") or {}
        serialized = str(diagnostics).lower()
        assert "provider" not in diagnostics
        assert "api_key" not in serialized
        assert "base_url" not in serialized
        assert "tok-secret" not in serialized
    finally:
        app.dependency_overrides = {}


def test_quality_diagnostics_top_deficiencies_are_secret_masked():
    from coaching import build_quality_diagnostics

    findings = [
        {"code": "MISSING_SECTION", "message": "raw token=abc123 leaked in deficiency"},
        {"code": "RESOURCE_LINKS_MISSING", "message": "api_key=sk-secret in hint"},
    ]
    diagnostics = build_quality_diagnostics({"score": 60, "structure_score": 80, "milestone_specificity_score": 60}, findings)
    serialized = str(diagnostics).lower()
    assert "abc123" not in serialized
    assert "sk-secret" not in serialized
    assert diagnostics["deficiency_count"] == 2


def test_default_project_charter_milestones_and_urls_remain_safe_and_secret_free():
    from coaching import build_sow_skeleton, sanitize_generated_sow

    sow = build_sow_skeleton(_base_intake(), parsed_jobs=[])
    sanitized, findings = sanitize_generated_sow(sow)

    assert not [f for f in findings if str(f.get("code") or "").startswith("UNSAFE_")]

    serialized = str(sanitized).lower()
    assert "api_key=" not in serialized
    assert "token=" not in serialized
    assert "password=" not in serialized

    for milestone in sanitized.get("milestones", []) or []:
        assert str(milestone.get("expected_deliverable") or "").strip()
        for resource in milestone.get("resources", []) or []:
            url = str((resource or {}).get("url") or "")
            if url:
                assert url.startswith("http://") or url.startswith("https://")
