from datetime import datetime, timezone

from fastapi.testclient import TestClient

import main
from auth import Session, get_current_session, issue_token
from main import app
from security import (
    FileValidationError,
    build_safe_resume_path,
    mask_secrets_in_text,
    mask_sensitive_dict,
    pii_hits,
    pii_safe_coaching_log_payload,
    pii_safe_text_summary,
    validate_resume_metadata,
)


def _override_editor_session():
    return Session(username="security-tester", role="editor", expires_at=datetime.now(timezone.utc))


def test_validate_resume_metadata_accepts_valid_pdf():
    out = validate_resume_metadata("resume.pdf", "application/pdf", 1024)
    assert out["accepted"] is True
    assert out["extension"] == ".pdf"


def test_validate_resume_metadata_rejects_executable():
    try:
        validate_resume_metadata("resume.exe", "application/octet-stream", 500)
        assert False, "Expected file validation error"
    except FileValidationError as e:
        assert "Unsupported" in str(e)


def test_safe_resume_path_blocks_traversal():
    safe = build_safe_resume_path("./storage/coaching/resumes", "ws-1", "../resume.pdf")
    assert ".." not in str(safe)


def test_mask_secret_helpers():
    text = "Authorization: Bearer abc.def.ghi token=supersecret"
    masked_text = mask_secrets_in_text(text)
    assert "supersecret" not in masked_text

    masked_dict = mask_sensitive_dict({"token": "abc", "nested": {"password": "pw"}})
    assert masked_dict["token"] == "***"
    assert masked_dict["nested"]["password"] == "***"


def test_pii_hits_basic():
    hits = pii_hits("email me at test@example.com or call 555-222-3333")
    assert hits["email"] >= 1
    assert hits["phone"] >= 1


def test_resume_validation_endpoint_baseline():
    app.dependency_overrides[get_current_session] = _override_editor_session
    client = TestClient(app)
    res = client.post(
        "/coaching/intake/resume/validate",
        json={
            "workspace_id": "coach-ws",
            "filename": "candidate_resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": 2048,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is True
    assert "safe_storage_path" in body
    app.dependency_overrides = {}


def _auth_header(role: str = "editor") -> dict[str, str]:
    token = issue_token(f"resume-{role}", role)
    return {"Authorization": f"Bearer {token}"}


def test_resume_validation_endpoint_requires_auth_contract():
    client = TestClient(app)
    res = client.post(
        "/coaching/intake/resume/validate",
        json={
            "workspace_id": "coach-ws",
            "filename": "candidate_resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": 2048,
        },
    )
    assert res.status_code == 401
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "auth_required"
    assert body["auth_required"] is True


def test_resume_validation_endpoint_denies_viewer_role_with_generic_payload():
    client = TestClient(app)
    res = client.post(
        "/coaching/intake/resume/validate",
        json={
            "workspace_id": "coach-ws",
            "filename": "candidate_resume.pdf",
            "content_type": "application/pdf",
            "size_bytes": 2048,
        },
        headers=_auth_header("viewer"),
    )
    assert res.status_code == 403
    body = res.json()
    assert body["ok"] is False
    assert body["code"] == "forbidden"
    assert body["auth_required"] is False


def test_resume_validation_endpoint_obeys_rate_limit_with_generic_429():
    snapshot = main.rate_limit_policy_snapshot()
    original = snapshot.get("policies", {}).get("subscription", {})
    client = TestClient(app)
    try:
        main.rate_limit_policy_update({"policies": {"subscription": {"rules": [{"limit": 1, "window_seconds": 60, "burst": 1}]}}})

        first = client.post(
            "/coaching/intake/resume/validate",
            json={
                "workspace_id": "coach-ws",
                "filename": "candidate_resume.pdf",
                "content_type": "application/pdf",
                "size_bytes": 2048,
            },
            headers=_auth_header("editor"),
        )
        assert first.status_code == 200

        second = client.post(
            "/coaching/intake/resume/validate",
            json={
                "workspace_id": "coach-ws",
                "filename": "candidate_resume.pdf",
                "content_type": "application/pdf",
                "size_bytes": 2048,
            },
            headers=_auth_header("editor"),
        )
        assert second.status_code == 429
        body = second.json()
        assert body["code"] == "rate_limited"
        assert body["auth_required"] is False
    finally:
        main.rate_limit_policy_update({"policies": {"subscription": original}})


def test_resume_validation_endpoint_masks_secret_like_filename_echoes():
    client = TestClient(app)
    res = client.post(
        "/coaching/intake/resume/validate",
        json={
            "workspace_id": "coach-ws",
            "filename": "token=super-secret-candidate.pdf",
            "content_type": "application/pdf",
            "size_bytes": 2048,
        },
        headers=_auth_header("editor"),
    )
    assert res.status_code == 200
    body = res.json()
    serialized = str(body).lower()
    assert "super-secret-candidate" not in serialized
    assert "token=***" in serialized


def test_pii_safe_text_summary_masks_content_to_metadata_only():
    summary = pii_safe_text_summary("Contact me at test@example.com 555-222-3333")
    assert summary["length"] > 0
    assert summary["pii_hits"]["email"] >= 1
    assert summary["pii_hits"]["phone"] >= 1
    assert "test@example.com" not in str(summary)


def test_pii_safe_coaching_log_payload_excludes_raw_resume_text():
    payload = pii_safe_coaching_log_payload(
        workspace_id="ws-1",
        submission_id="sub-1",
        applicant_name="Candidate",
        applicant_email="candidate@example.com",
        resume_text="This is raw resume text with Spark and private details",
        self_assessment_text="I need help",
        job_links=["https://example.com/job/1"],
        parsed_jobs=[{"source": "live", "signals": {"skills": ["python"]}}],
    )
    serialized = str(payload)
    assert "raw resume text" not in serialized
    assert payload["resume_text_summary"]["length"] > 0
    assert payload["job_link_count"] == 1
    assert payload["parsed_jobs_count"] == 1
