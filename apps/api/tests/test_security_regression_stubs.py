import pytest


@pytest.mark.skip(reason="Security regression stub: add multipart upload + MIME sniff tests when resume upload endpoint is implemented")
def test_resume_upload_rejects_polyglot_file_stub():
    pass


@pytest.mark.skip(reason="Security regression stub: add auth/RBAC privilege-escalation checks for coaching intake endpoints")
def test_coaching_intake_rbac_regression_stub():
    pass


@pytest.mark.skip(reason="Security regression stub: add export/log masking check after coaching export endpoint is implemented")
def test_export_masks_pii_and_secrets_stub():
    pass
