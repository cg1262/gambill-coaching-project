from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching import validate_sow_payload, build_sow_skeleton, evaluate_sow_structure
from main import app
from models import CoachingSowDraft


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


def test_structure_evaluator_flags_missing_and_order_mismatch():
    sow = {
        "schema_version": "0.2",
        "project_title": "Example",
        "business_outcome": {},
        "candidate_profile": {},
        "solution_architecture": {},
    }
    structure = evaluate_sow_structure(sow)
    assert "milestones" in structure["missing_sections"]
    assert structure["order_valid"] is False
    assert structure["structure_score"] < 100



def test_validator_flags_section_order_invalid():
    sow = build_sow_skeleton(
        intake={"applicant_name": "Candidate", "preferences": {}},
        parsed_jobs=[],
    )
    reordered = {
        "schema_version": sow["schema_version"],
        "project_title": sow["project_title"],
        "candidate_profile": sow["candidate_profile"],
        "solution_architecture": sow["solution_architecture"],
        "business_outcome": sow["business_outcome"],
        "project_story": sow["project_story"],
        "milestones": sow["milestones"],
        "roi_dashboard_requirements": sow["roi_dashboard_requirements"],
        "resource_plan": sow["resource_plan"],
        "mentoring_cta": sow["mentoring_cta"],
    }
    structure = evaluate_sow_structure(reordered)
    assert structure["order_valid"] is False

    codes = {f["code"] for f in validate_sow_payload(reordered)}
    assert "SECTION_ORDER_INVALID" not in codes


def test_coaching_sow_model_roundtrip_keeps_required_top_level_order():
    sow = build_sow_skeleton(
        intake={"applicant_name": "Candidate", "preferences": {}},
        parsed_jobs=[],
    )
    strict = CoachingSowDraft.model_validate(sow).model_dump(mode="json", by_alias=True)
    codes = {f["code"] for f in validate_sow_payload(strict)}
    assert "SECTION_ORDER_INVALID" not in codes


def test_skeleton_data_sources_include_public_links_docs_and_rationale():
    sow = build_sow_skeleton(
        intake={"applicant_name": "Candidate", "preferences": {"stack": ["python"], "tool_preferences": ["power bi"]}},
        parsed_jobs=[{"signals": {"skills": ["SQL"], "tools": ["Power BI"], "domains": ["transport"]}}],
    )
    data_sources = sow["business_outcome"]["data_sources"]
    assert len(data_sources) >= 1
    for source in data_sources:
        assert str(source.get("url") or "").startswith("https://")
        assert str(source.get("ingestion_doc_url") or "").startswith("https://")
        assert str(source.get("selection_rationale") or "").strip()


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
            "meta": {
                "provider": "openai-compatible",
                "model": "gpt-test",
                "meta_rubric_gate": {
                    "threshold": 85,
                    "initial_overall_score": 72,
                    "final_overall_score": 88,
                    "met_threshold_initially": False,
                    "met_threshold_final": True,
                    "reprocessed": True,
                    "reprocess_attempts": [{"archetype": "energy", "overall_score": 88}],
                    "selected_archetype": "energy",
                    "status": "reprocessed_pass",
                },
            },
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
    assert "structure_score" in body["quality"]
    assert "missing_sections" in body["quality"]
    assert captured["validation"]["generation_meta"]["provider"] == "openai-compatible"
    assert captured["validation"]["generation_meta"]["meta_rubric_gate"]["status"] == "reprocessed_pass"
    assert int(captured["validation"]["generation_meta"]["meta_rubric_gate"]["final_overall_score"]) == 88
    assert "quality_flags" in captured["validation"]

    app.dependency_overrides = {}


def test_generate_sow_persists_meta_rubric_gate_in_saved_validation(monkeypatch):
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
            "sow": build_sow_skeleton(intake, parsed_jobs),
            "meta": {
                "provider": "openai-compatible",
                "model": "gpt-test",
                "meta_rubric_gate": {
                    "threshold": 85,
                    "initial_overall_score": 68,
                    "final_overall_score": 86,
                    "met_threshold_initially": False,
                    "met_threshold_final": True,
                    "reprocessed": True,
                    "reprocess_attempts": [{"archetype": "finance", "overall_score": 86}],
                    "selected_archetype": "finance",
                    "status": "reprocessed_pass",
                    "max_reprocess_attempts": 2,
                    "archetype_order": ["finance", "energy", "retail", "general"],
                },
            },
        },
    )

    captured = {}
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: captured.update(kwargs))

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": "sub-persist", "parsed_jobs": []},
    )
    assert res.status_code == 200
    body = res.json()
    gate_meta = body["generation_meta"]["meta_rubric_gate"]
    assert gate_meta["status"] == "reprocessed_pass"
    assert gate_meta["selected_archetype"] == "finance"
    assert gate_meta["archetype_order"] == ["finance", "energy", "retail", "general"]

    persisted_gate = captured["validation"]["generation_meta"]["meta_rubric_gate"]
    assert persisted_gate["status"] == "reprocessed_pass"
    assert int(persisted_gate["final_overall_score"]) == 86
    assert persisted_gate["reprocess_attempts"][0]["archetype"] == "finance"
    assert int(persisted_gate["max_reprocess_attempts"]) == 2

    app.dependency_overrides = {}


def test_generate_sow_surfaces_fallback_mode_and_reason_codes_on_quality_gate(monkeypatch):
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
            "sow": build_sow_skeleton(intake, parsed_jobs),
            "meta": {"provider": "openai-compatible", "model": "gpt-test"},
        },
    )
    monkeypatch.setattr(
        main,
        "compute_sow_quality_score",
        lambda sow, findings: {"score": 35, "structure_score": 30, "missing_sections": [], "section_order_valid": True, "style_alignment_score": 20, "milestone_specificity_score": 25},
    )
    monkeypatch.setattr(main, "save_coaching_generation_run", lambda **kwargs: None)

    client = TestClient(app)
    res = client.post(
        "/coaching/sow/generate",
        json={"workspace_id": "ws-1", "submission_id": "sub-llm", "parsed_jobs": []},
    )
    assert res.status_code == 200
    body = res.json()

    assert body["generation_mode"] == "fallback_scaffold"
    assert "HARD_QUALITY_GATE_TRIGGERED" in body["generation_reason_codes"]
    assert body["quality_flags"]["fallback_used"] is True
    assert body["quality_flags"]["generation_mode"] == "fallback_scaffold"
    prereq_summary = body["sow"]["project_charter"]["sections"]["prerequisites_resources"]["summary"]
    assert isinstance(prereq_summary, str) and len(prereq_summary) >= 40
    assert "source" in prereq_summary.lower()
    bronze_plan = body["sow"]["solution_architecture"]["medallion_plan"]["bronze"]
    assert isinstance(bronze_plan, str) and len(bronze_plan) >= 30
    assert "load" in bronze_plan.lower() or "source" in bronze_plan.lower()

    app.dependency_overrides = {}
