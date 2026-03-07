import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching.sprint14_artifacts import build_seeded_quality_trend_report
from main import app


TREND_FILE = Path(__file__).parent / "fixtures" / "sprint16_seeded_quality_trend_report.json"


def _override_session(role: str = "admin", username: str = "coach-s16"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def setup_function():
    app.dependency_overrides = {}


def test_sprint16_seeded_quality_trend_report_enforces_production_bar():
    generated = build_seeded_quality_trend_report()
    committed = json.loads(TREND_FILE.read_text(encoding="utf-8"))

    assert generated == committed
    assert committed["report_version"] == "2026-03-sprint16"
    assert committed["production_gate"]["all_seeded_scenarios_pass"] is True
    assert committed["production_gate"]["zero_major_deficiencies"] is True
    assert committed["fail_count"] == 0


def test_sprint16_batch_endpoints_include_coach_audit_metadata(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("admin", "coach-s16")
    monkeypatch.setattr(main, "_apply_rate_limit", lambda **kwargs: None)
    monkeypatch.setattr(main, "_require_active_coaching_subscription", lambda **kwargs: {"ok": True})
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: {"submission_id": submission_id, "applicant_email": "x@example.com"})
    monkeypatch.setattr(
        main,
        "_persist_review_state_with_retry",
        lambda **kwargs: {"ok": True, "attempts": 1, "submission": {"submission_id": kwargs["submission_id"], "coach_review_status": kwargs["coach_review_status"]}},
    )

    def _fake_generate(req, request, session):
        return {
            "ok": True,
            "run_id": f"run-{req.submission_id}",
            "quality": {"score": 87},
            "findings": [],
            "quality_flags": {"hard_quality_gate_triggered": False},
        }

    monkeypatch.setattr(main, "coaching_generate_sow", _fake_generate)

    client = TestClient(app)

    status_res = client.post(
        "/coaching/review/batch-status",
        json={"workspace_id": "ws-1", "submission_ids": ["sub-1", "sub-1", "sub-2"], "coach_review_status": "in_review", "coach_notes": "batch"},
    )
    assert status_res.status_code == 200
    status_body = status_res.json()
    assert status_body["audit"]["action"] == "batch_review_status_update"
    assert status_body["audit"]["actor"] == "coach-s16"
    assert status_body["audit"]["requested_submissions"] == 3
    assert status_body["audit"]["deduped_submissions"] == 2
    assert all((row.get("audit") or {}).get("batch_id") == status_body["audit"]["batch_id"] for row in status_body["updated"])

    regen_res = client.post(
        "/coaching/sow/batch-regenerate",
        json={"workspace_id": "ws-1", "submission_ids": ["sub-1", "sub-1", "sub-2"], "parsed_jobs": [], "regenerate_with_improvements": True},
    )
    assert regen_res.status_code == 200
    regen_body = regen_res.json()
    assert regen_body["audit"]["action"] == "batch_regenerate"
    assert regen_body["audit"]["requested_submissions"] == 3
    assert regen_body["audit"]["deduped_submissions"] == 2
    assert all((row.get("audit") or {}).get("batch_id") == regen_body["audit"]["batch_id"] for row in regen_body["runs"])


def test_sprint16_weekly_summary_uses_unique_submission_stage_counts(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("viewer", "coach-s16")
    now = datetime.now(timezone.utc).isoformat()
    monkeypatch.setattr(
        main,
        "list_coaching_conversion_events_window",
        lambda **kwargs: [
            {"event_name": "intake_completed", "created_at": now, "submission_id": "sub-1"},
            {"event_name": "intake_completed", "created_at": now, "submission_id": "sub-1"},
            {"event_name": "sow_generated", "created_at": now, "submission_id": "sub-1"},
            {"event_name": "sow_regenerated", "created_at": now, "submission_id": "sub-1"},
            {"event_name": "sow_exported", "created_at": now, "submission_id": "sub-1"},
            {"event_name": "cta_click", "created_at": now, "submission_id": "sub-1"},
        ],
    )

    client = TestClient(app)
    res = client.get("/coaching/conversion/weekly-summary", params={"workspace_id": "ws-1", "lookback_days": 7})
    assert res.status_code == 200
    body = res.json()
    assert body["counts"]["intake_completed"] == 1
    assert body["counts"]["sow_generated"] == 1
    assert body["counts"]["sow_regenerated"] == 1
    assert body["raw_event_counts"]["intake_completed"] == 2
    assert body["conversion_rates"]["generate_rate"] == 1.0
    assert body["conversion_rates"]["export_rate"] == 1.0
    assert body["conversion_rates"]["cta_rate"] == 1.0
