from datetime import datetime, timezone

from fastapi.testclient import TestClient

from auth import Session, get_current_session
from main import app
from security import (
    FileValidationError,
    build_safe_resume_path,
    mask_secrets_in_text,
    mask_sensitive_dict,
    pii_hits,
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
