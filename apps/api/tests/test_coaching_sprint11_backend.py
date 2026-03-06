from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching import build_sow_skeleton, build_quality_diagnostics, extract_resume_signals, validate_sow_payload
from main import CoachingIntakeRequest, app
from rate_limits import RATE_LIMIT_STORE


def _override_session(role: str = "editor", username: str = "sprint11"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def setup_function():
    RATE_LIMIT_STORE.reset()
    app.dependency_overrides = {}


def test_resume_signal_parser_emits_confidence_and_role_evidence():
    out = extract_resume_signals(
        "Senior data engineer with 9 years experience using Python SQL dbt Airflow and AWS in fintech analytics."
    )
    assert int(out.get("parse_confidence") or 0) >= 50
    assert isinstance(out.get("role_evidence"), list)
    assert out.get("role_level") in {"mid", "senior"}


def test_preferences_accept_editable_resume_profile_fields():
    payload = CoachingIntakeRequest(
        workspace_id="ws-1",
        applicant_name="Alex",
        applicant_email="alex@example.com",
        resume_text="resume",
        self_assessment_text="notes",
        preferences={
            "target_role": "Senior Data Engineer",
            "timeline_weeks": 8,
            "resume_profile": {"headline": "Data engineer"},
            "combined_profile": {"focus": ["platform", "analytics"]},
            "profile_overrides": {"role_level": "mid"},
            "resume_parse_summary": {"role_level": "mid", "parse_confidence": 71},
            "stack_preferences": ["python"],
            "tool_preferences": ["dbt"],
        },
    )
    assert payload.preferences["resume_profile"]["headline"] == "Data engineer"


def test_quality_diagnostics_exposes_actionable_fail_reasons_for_acceptance_checks():
    sow = build_sow_skeleton(intake={"applicant_name": "Alex", "preferences": {}}, parsed_jobs=[])
    sow["milestones"][0]["acceptance_checks"] = ["Looks good", "Done"]
    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}
    assert "MILESTONE_ACCEPTANCE_CHECKS_NOT_ACTIONABLE" in codes

    diagnostics = build_quality_diagnostics({"score": 72, "structure_score": 95, "milestone_specificity_score": 74, "style_alignment_score": 80}, findings)
    assert diagnostics["actionable_fail_reasons"]
    assert any(r.get("code") == "MILESTONE_ACCEPTANCE_CHECKS_NOT_ACTIONABLE" for r in diagnostics["actionable_fail_reasons"])


def test_conversion_weekly_summary_rolls_up_core_funnel_events(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "coach-s11")

    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        main,
        "list_coaching_conversion_events_window",
        lambda **kwargs: [
            {"event_name": "intake_completed", "created_at": now},
            {"event_name": "sow_generated", "created_at": now},
            {"event_name": "sow_exported", "created_at": now},
            {"event_name": "cta_click", "created_at": now},
        ],
    )

    client = TestClient(app)
    res = client.get("/coaching/conversion/weekly-summary", params={"workspace_id": "ws-1", "lookback_days": 7})
    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["intake_completed"] == 1
    assert body["counts"]["sow_generated"] == 1
    assert body["counts"]["sow_exported"] == 1
    assert body["counts"]["cta_click"] == 1
