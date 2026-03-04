from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session
from coaching import CHARTER_REQUIRED_SECTION_FLOW, build_sow_skeleton, validate_sow_payload
from main import app
from rate_limits import RATE_LIMIT_STORE


def _override_session(role: str = "editor", username: str = "sprint9"):
    def _inner():
        return Session(username=username, role=role, expires_at=datetime.now(timezone.utc))

    return _inner


def setup_function():
    RATE_LIMIT_STORE.reset()
    app.dependency_overrides = {}


def test_resume_upload_txt_extracts_and_returns_parse_summary(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-s9")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: None)

    client = TestClient(app)
    payload = b"Senior data engineer with 8 years experience in Python SQL dbt Airflow and healthcare analytics."
    resp = client.post(
        "/coaching/intake/resume/upload",
        data={"workspace_id": "ws-1"},
        files={"file": ("resume.txt", payload, "text/plain")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "resume_text" in body and "Senior data engineer" in body["resume_text"]
    summary = body["resume_parse_summary"]
    assert summary["fallback_used"] is False
    assert summary["role_level"] in {"mid", "senior"}
    assert "python" in summary["tools"]


def test_resume_upload_pdf_fallback_sets_warning(monkeypatch):
    app.dependency_overrides[get_current_session] = _override_session("editor", "coach-s9")
    monkeypatch.setattr(main, "get_coaching_intake_submission", lambda submission_id: None)

    client = TestClient(app)
    # minimal bytes with almost no extractable text
    resp = client.post(
        "/coaching/intake/resume/upload",
        data={"workspace_id": "ws-1"},
        files={"file": ("resume.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["resume_parse_summary"]["fallback_used"] is True
    assert "parse_warning" in body["resume_parse_summary"]


def test_validator_enforces_globalmart_charter_section_order():
    sow = build_sow_skeleton(intake={"applicant_name": "Alex", "preferences": {}}, parsed_jobs=[])
    findings = validate_sow_payload(sow)
    codes = {f.get("code") for f in findings}
    assert "CHARTER_SECTION_ORDER_INVALID" not in codes
    assert list((sow.get("project_charter") or {}).get("section_order") or []) == list(CHARTER_REQUIRED_SECTION_FLOW)

    tampered = dict(sow)
    tampered["project_charter"] = dict(sow["project_charter"])
    tampered["project_charter"]["section_order"] = list(reversed(CHARTER_REQUIRED_SECTION_FLOW))
    findings_bad = validate_sow_payload(tampered)
    bad_codes = {f.get("code") for f in findings_bad}
    assert "CHARTER_SECTION_ORDER_INVALID" in bad_codes
