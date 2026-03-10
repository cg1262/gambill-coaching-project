

def test_sanitize_generated_sow_handles_string_mentoring_cta():
    from coaching import sanitize_generated_sow

    payload = {
        "project_title": "Test",
        "resource_plan": {},
        "mentoring_cta": "Book a call with token=abc123",
    }

    sanitized, findings = sanitize_generated_sow(payload)
    assert isinstance(sanitized.get("mentoring_cta"), dict)
    assert "Book a call" in str((sanitized.get("mentoring_cta") or {}).get("reason") or "")
    assert "abc123" not in str((sanitized.get("mentoring_cta") or {}).get("reason") or "")
    assert isinstance(findings, list)
