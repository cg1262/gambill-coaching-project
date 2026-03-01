import pytest


@pytest.mark.skip(reason="Security regression stub: add multipart upload + MIME sniff tests when resume upload endpoint is implemented")
def test_resume_upload_rejects_polyglot_file_stub():
    pass


@pytest.mark.skip(reason="Threat-guard stub: add multipart content-type enforcement test for malicious upload payloads")
def test_resume_upload_rejects_malicious_content_type_stub():
    pass


@pytest.mark.skip(reason="Threat-guard stub: add oversized multipart payload rejection test in live upload endpoint")
def test_resume_upload_rejects_oversized_payload_stub():
    pass


@pytest.mark.skip(reason="Security regression stub: add export/log masking check after coaching export endpoint is implemented")
def test_export_masks_pii_and_secrets_stub():
    pass
