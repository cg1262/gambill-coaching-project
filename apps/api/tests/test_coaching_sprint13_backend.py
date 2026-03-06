import json
from pathlib import Path
from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching import build_sow_skeleton, build_quality_diagnostics, extract_resume_signals, validate_sow_payload, compute_sow_quality_score
from main import app


SNAPSHOT_FILE = Path(__file__).parent / "fixtures" / "sprint13_golden_sow_snapshots.json"


def _golden_intake(name: str, role_level: str, years: int, tools: list[str], domains: list[str], timeline_weeks: int = 6):
    return {
        "applicant_name": name,
        "preferences": {
            "timeline_weeks": timeline_weeks,
            "resume_parse_summary": {
                "role_level": role_level,
                "years_experience_hint": years,
                "parse_confidence": 82,
                "tools": tools,
                "domains": domains,
                "project_experience_keywords": ["medallion", "kpi", "data quality", "orchestration"],
            },
        },
    }


def _case_inputs():
    return {
        "globalmart": {
            "intake": _golden_intake("Avery", "senior", 9, ["python", "sql", "dbt", "airflow", "aws", "power bi"], ["retail", "ecommerce"]),
            "parsed_jobs": [{"signals": {"seniority": "senior", "skills": ["sql"], "tools": ["dbt"], "domains": ["retail"]}}],
        },
        "voltstream": {
            "intake": _golden_intake("Morgan", "mid", 6, ["python", "sql", "spark", "databricks", "azure"], ["energy", "telecom"]),
            "parsed_jobs": [{"signals": {"seniority": "senior", "skills": ["spark"], "tools": ["databricks"], "domains": ["energy"]}}],
        },
        "foundational": {
            "intake": _golden_intake("Jordan", "junior", 1, ["python", "sql"], ["healthcare"], timeline_weeks=10),
            "parsed_jobs": [{"signals": {"seniority": "mid", "skills": ["sql"], "tools": ["airflow"], "domains": ["healthcare"]}}],
        },
        "advanced_finops": {
            "intake": _golden_intake("Casey", "senior", 12, ["python", "sql", "dbt", "airflow", "aws", "spark", "databricks"], ["finance", "saas"], timeline_weeks=5),
            "parsed_jobs": [{"signals": {"seniority": "senior", "skills": ["spark", "sql"], "tools": ["databricks", "dbt"], "domains": ["finance"]}}],
        },
    }


def test_sprint13_golden_snapshots_fail_on_major_style_or_structure_drift():
    snapshots = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    for case_name, cfg in _case_inputs().items():
        sow = build_sow_skeleton(intake=cfg["intake"], parsed_jobs=cfg["parsed_jobs"])
        findings = validate_sow_payload(sow)
        quality = compute_sow_quality_score(sow, findings)
        diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-golden", submission_id=f"sub-{case_name}")

        expected = snapshots[case_name]
        assert sow["project_title"] == expected["project_title"]
        assert ((sow.get("candidate_profile") or {}).get("role_scope_assessment") or {}) == expected["scope"]
        assert (sow.get("project_story") or {}) == expected["story"]
        assert (((sow.get("project_charter") or {}).get("sections") or {}).get("executive_summary") or {}) == expected["charter_exec"]
        assert [m.get("name") for m in (sow.get("milestones") or [])] == expected["milestone_names"]
        assert [d.get("name") for d in ((sow.get("business_outcome") or {}).get("data_sources") or [])] == expected["data_source_names"]

        assert diagnostics["major_deficiency_count"] == 0
        assert quality["style_alignment_score"] >= 80


def test_sprint13_resume_parse_confidence_explainability_payload_present():
    out = extract_resume_signals("Senior data engineer with 10 years using Python SQL dbt Airflow AWS in fintech KPI analytics.")
    explain = out.get("parse_confidence_explainability") or {}

    assert isinstance(explain.get("factors"), list)
    assert len(explain.get("factors") or []) >= 4
    assert explain.get("confidence_band") in {"low", "medium", "high"}


def test_sprint13_regenerate_payload_contract_carries_deficiency_context():
    sow = build_sow_skeleton(intake=_golden_intake("Riley", "mid", 5, ["python", "sql", "dbt"], ["finance"]), parsed_jobs=[])
    sow["milestones"][0]["acceptance_checks"] = ["looks good"]
    findings = validate_sow_payload(sow)
    quality = compute_sow_quality_score(sow, findings)
    diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-13", submission_id="sub-13")

    payload = diagnostics.get("regenerate_payload") or {}
    assert payload.get("contract_version") == "2026-03-sprint13"
    assert payload.get("body", {}).get("deficiency_context", {}).get("deficiency_codes")
    assert payload.get("body", {}).get("regenerate_with_improvements") is True


def _override_session(role: str = "viewer", username: str = "coach-s13"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def test_sprint13_weekly_summary_includes_drop_off_insights(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "coach-s13")
    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        main,
        "list_coaching_conversion_events_window",
        lambda **kwargs: [
            {"event_name": "intake_completed", "created_at": now},
            {"event_name": "intake_completed", "created_at": now},
            {"event_name": "sow_generated", "created_at": now},
            {"event_name": "sow_exported", "created_at": now},
        ],
    )

    client = TestClient(app)
    res = client.get("/coaching/conversion/weekly-summary", params={"workspace_id": "ws-1", "lookback_days": 7})
    assert res.status_code == 200
    body = res.json()
    top = (((body.get("drop_off_insights") or {}).get("top_drop_offs") or [{}])[0])
    assert top.get("drop_off_count") >= 1
    assert top.get("from_stage") == "intake_completed"

    app.dependency_overrides = {}


def test_sprint13_validation_flags_low_personalization_when_resume_signals_ignored():
    intake = {
        "applicant_name": "Taylor",
        "preferences": {
            "resume_parse_summary": {
                "role_level": "senior",
                "years_experience_hint": 11,
                "parse_confidence": 82,
                "tools": ["fivetran", "matillion", "stitch"],
                "domains": ["insurance", "telecom"],
                "project_experience_keywords": ["streaming", "mlops", "forecast"],
            }
        },
    }
    sow = build_sow_skeleton(intake=intake, parsed_jobs=[])
    sow["solution_architecture"]["primary_tools"] = ["excel"]
    sow["business_outcome"]["domain_focus"] = ["education"]
    sow["project_story"]["executive_summary"] = "Build a generic data project."
    sow["project_story"]["impact_story"] = "Show an outcome."

    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}
    assert "PERSONALIZATION_SIGNAL_MISSING" in codes
