from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching import sow_draft
from main import app


def _override_session(role: str = "editor", username: str = "sprint18"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def _base_submission(submission_id: str = "sub-1") -> dict:
    return {
        "submission_id": submission_id,
        "workspace_id": "ws-1",
        "applicant_name": "Candidate One",
        "applicant_email": "candidate@example.com",
        "preferences_json": {},
        "resume_text": "",
        "self_assessment_text": "",
    }


def test_sow_evaluate_accepts_request_payload(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})

    sow = main.build_sow_skeleton({"applicant_name": "Candidate One", "preferences": {}}, [])
    client = TestClient(app)
    res = client.post(
        "/coaching/sow/evaluate",
        json={"workspace_id": "ws-1", "sow": sow},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["source"] == "request"
    assert isinstance(body["evaluation"]["overall_score"], int)
    assert body["evaluation"]["rubric_version"] == "2026-03-generation-meta-rubric-v1"
    assert body["evaluation"]["meta_rubric"]["rubric_type"] == "generation_meta_rubric"
    assert len(body["evaluation"]["meta_rubric"]["metrics"]) == 10
    app.dependency_overrides = {}


def test_sow_evaluate_uses_run_id_payload(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(
        main,
        "get_coaching_generation_run",
        lambda run_id: {
            "run_id": run_id,
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "sow_json": main.build_sow_skeleton({"applicant_name": "Candidate One", "preferences": {}}, []),
        },
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/evaluate",
        json={"workspace_id": "ws-1", "run_id": "run-1"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["source"] == "run"
    assert body["run_id"] == "run-1"
    app.dependency_overrides = {}


def test_export_uses_run_id_when_sow_missing(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_submission(submission_id))
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)
    monkeypatch.setattr(
        main,
        "get_coaching_generation_run",
        lambda run_id: {
            "run_id": run_id,
            "workspace_id": "ws-1",
            "submission_id": "sub-1",
            "sow_json": main.build_sow_skeleton({"applicant_name": "Candidate One", "preferences": {}}, []),
        },
    )

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/export",
        json={"workspace_id": "ws-1", "submission_id": "sub-1", "run_id": "run-1", "format": "json"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert body["format"] == "json"
    assert body["run_id"] == "run-1"
    assert '"project_title"' in str(body["content"])
    app.dependency_overrides = {}


def test_generate_sanitizes_review_meta_for_response_and_persistence(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor")
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"subscription_status": "active"})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: _base_submission(submission_id))
    monkeypatch.setattr(
        main,
        "generate_sow_with_llm",
        lambda intake, parsed_jobs: {
            "ok": True,
            "sow": main.build_sow_skeleton(intake, parsed_jobs),
            "meta": {
                "provider": "openai-compatible",
                "model": "gpt-test",
                "usage": {"prompt_tokens": 200, "completion_tokens": 150, "total_tokens": 350},
                "review": {
                    "attempted": True,
                    "applied": False,
                    "reason": "no_improvement",
                    "quality_before": {"score": 81, "finding_count": 2, "extra": "ignored"},
                    "quality_after": {"score": 81, "finding_count": 2},
                    "usage": {"prompt_tokens": 50, "completion_tokens": 25, "total_tokens": 75},
                    "review_finish_reason": "stop",
                },
            },
        },
    )
    monkeypatch.setattr(main, "list_coaching_generation_runs", lambda submission_id, limit=1: [])
    monkeypatch.setattr(main, "list_recent_coaching_feedback_events", lambda submission_id, limit=3: [])
    monkeypatch.setattr(main, "save_coaching_conversion_event", lambda **kwargs: None)

    captured: dict = {}

    def _capture_run(**kwargs):
        captured.update(kwargs)

    monkeypatch.setattr(main, "save_coaching_generation_run", _capture_run)

    client = TestClient(app)
    res = client.post("/coaching/sow/generate", json={"workspace_id": "ws-1", "submission_id": "sub-1", "parsed_jobs": []})
    assert res.status_code == 200
    body = res.json()
    review = (body["generation_meta"] or {}).get("review") or {}
    assert review["attempted"] is True
    assert review["applied"] is False
    assert review["reason"] == "no_improvement"
    assert (review.get("quality_before") or {}).get("score") == 81
    assert (review.get("usage") or {}).get("total_tokens") == 75
    assert review.get("review_finish_reason") == "stop"

    persisted_review = (((captured.get("validation") or {}).get("generation_meta") or {}).get("review") or {})
    assert persisted_review.get("attempted") is True
    assert persisted_review.get("reason") == "no_improvement"
    app.dependency_overrides = {}


def test_sow_draft_review_pass_applies_improved_output(monkeypatch):
    intake = {
        "applicant_name": "Candidate One",
        "resume_text": "",
        "self_assessment_text": "",
        "preferences": {},
    }
    parsed_jobs: list[dict] = []
    draft_sow = sow_draft.build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs)
    reviewed_sow = sow_draft.build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs)
    draft_sow["project_title"] = "Draft Project"
    reviewed_sow["project_title"] = "Improved Project"

    responses = [
        (
            {"archetype": "general", "dashboard_questions": ["q1", "q2", "q3"]},
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 40, "completion_tokens": 20, "total_tokens": 60}},
        ),
        (
            draft_sow,
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 110, "completion_tokens": 90, "total_tokens": 200}},
        ),
        (
            reviewed_sow,
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 50, "completion_tokens": 30, "total_tokens": 80}},
        ),
    ]

    def _fake_request_llm_json(**kwargs):
        return responses.pop(0)

    def _fake_validate(payload):
        title = str(payload.get("project_title") or "")
        return [{"code": "QUALITY"}] if "Draft" in title else []

    def _fake_quality(payload, findings):
        title = str(payload.get("project_title") or "")
        if "Draft" in title:
            return {"score": 72, "finding_count": len(findings)}
        return {"score": 91, "finding_count": len(findings)}

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("COACHING_SOW_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("COACHING_SOW_ENABLE_REVIEW_PASS", "1")
    monkeypatch.setattr(sow_draft, "_request_llm_json", _fake_request_llm_json)
    monkeypatch.setattr(sow_draft, "validate_sow_payload", _fake_validate)
    monkeypatch.setattr(sow_draft, "compute_sow_quality_score", _fake_quality)

    result = sow_draft.generate_sow_with_llm(intake=intake, parsed_jobs=parsed_jobs, timeout=2, max_retries=0)
    assert result["ok"] is True
    assert result["sow"]["project_title"] == "Improved Project"
    review = (result.get("meta") or {}).get("review") or {}
    assert review.get("attempted") is True
    assert review.get("applied") is True
    assert review.get("reason") == "improved"


def test_sow_draft_accepts_llm_api_key_alias(monkeypatch):
    intake = {
        "applicant_name": "Candidate One",
        "resume_text": "",
        "self_assessment_text": "",
        "preferences": {},
    }
    parsed_jobs: list[dict] = []
    expected_sow = sow_draft.build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs)
    captured: list[str] = []
    responses = [
        (
            {"archetype": "general", "dashboard_questions": ["q1", "q2", "q3"]},
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ),
        (
            expected_sow,
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}},
        ),
    ]

    def _fake_request_llm_json(**kwargs):
        captured.append(str(kwargs.get("api_key") or ""))
        return responses.pop(0)

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("LLM_API_KEY", "alias-key")
    monkeypatch.setenv("COACHING_SOW_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("COACHING_SOW_ENABLE_REVIEW_PASS", "0")
    monkeypatch.setattr(sow_draft, "_request_llm_json", _fake_request_llm_json)

    result = sow_draft.generate_sow_with_llm(intake=intake, parsed_jobs=parsed_jobs, timeout=2, max_retries=0)

    assert result["ok"] is True
    assert captured == ["alias-key", "alias-key"]
    assert (result.get("meta") or {}).get("api_key_source") == "LLM_API_KEY"


def test_sow_draft_sends_explicit_output_templates_in_prompt_payload(monkeypatch):
    intake = {
        "applicant_name": "Candidate One",
        "resume_text": "Lead data engineer with insurance analytics background.",
        "self_assessment_text": "Strong in Databricks, Spark, and KPI storytelling.",
        "preferences": {"resume_parse_summary": {"domains": ["insurance"]}},
    }
    parsed_jobs: list[dict] = [{"signals": {"domains": ["insurance"], "tools": ["Databricks", "Power BI"]}}]
    expected_sow = sow_draft.build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs)
    captured_payloads: list[dict] = []
    responses = [
        (
            {
                "archetype": "finance",
                "candidate_fit_summary": "Fits well.",
                "project_focus": "Claims analytics modernization.",
                "business_problem": "Claims reporting latency.",
                "recommended_source_names": ["Insurance Data API"],
                "requested_industry": "insurance",
                "dashboard_questions": ["Which regions are exceeding claims cycle targets?"],
                "delivery_scope": {"target_role_level": "lead", "scope_difficulty": "advanced", "suggested_timeline_weeks": 8},
                "self_assessment_takeaways": {"strengths": ["spark"], "gaps": [], "notes": "Strong platform fit."},
                "industry_context": {"primary": "insurance", "all_domains": ["insurance"], "source": "resume_or_job_domains"},
            },
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}},
        ),
        (
            expected_sow,
            {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 20, "completion_tokens": 15, "total_tokens": 35}},
        ),
    ]

    def _fake_request_llm_json(**kwargs):
        captured_payloads.append(kwargs.get("user_payload") or {})
        return responses.pop(0)

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("COACHING_SOW_LLM_MODEL", "gpt-test")
    monkeypatch.setenv("COACHING_SOW_ENABLE_REVIEW_PASS", "0")
    monkeypatch.setattr(sow_draft, "_request_llm_json", _fake_request_llm_json)

    result = sow_draft.generate_sow_with_llm(intake=intake, parsed_jobs=parsed_jobs, timeout=2, max_retries=0)

    assert result["ok"] is True
    assert len(captured_payloads) == 2
    strategy_payload = captured_payloads[0]
    sow_payload = captured_payloads[1]
    assert "output_template" in strategy_payload
    assert "requested_industry" in (strategy_payload.get("output_template") or {})
    assert "industry_context" in (strategy_payload.get("output_template") or {})
    assert "output_template" in sow_payload
    assert "schema_version" in (sow_payload.get("output_template") or {})
    assert "project_charter" in (sow_payload.get("output_template") or {})
    assert "sections" in ((sow_payload.get("output_template") or {}).get("project_charter") or {})
    assert "medallion_plan" in ((sow_payload.get("output_template") or {}).get("solution_architecture") or {})
