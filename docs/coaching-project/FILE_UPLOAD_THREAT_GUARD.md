# File Upload Threat Guard (Coaching Resume Intake)

Last Updated: 2026-03-01
Owner: Security Agent

## Goal
Prevent risky file payloads from entering coaching workflows by enforcing deterministic metadata checks now, with multipart byte-level validation planned next.

## Current Controls (Implemented)
- Allowed extensions only: `.pdf`, `.doc`, `.docx`, `.txt`
- Allowed MIME content-types only:
  - `application/pdf`
  - `application/msword`
  - `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `text/plain`
- Maximum payload size: **5 MB**
- Empty file rejection
- Safe storage path construction (workspace + basename sanitization)

## Threat Scenarios + Handling
1. **Malicious content type spoofing**
   - Current: blocked by metadata allowlist in `validate_resume_metadata`.
   - Next: enforce byte-level MIME sniffing on uploaded bytes.
2. **Oversize payload abuse / resource exhaustion**
   - Current: blocked by max byte limit (`DEFAULT_MAX_RESUME_BYTES`).
   - Next: enforce request body size limits and streaming guards on multipart endpoint.
3. **Polyglot/embedded executable payloads**
   - Current: not fully mitigated without byte scanning.
   - Next: add signature checks + malware scanning hook.

## Test Coverage
- Implemented baseline tests in `apps/api/tests/test_security_baseline.py` for allowlist and path safety.
- Added regression stubs in `apps/api/tests/test_security_regression_stubs.py` for:
  - malicious content-type multipart uploads
  - oversize multipart payload rejection
  - polyglot payload rejection

## Engineering Follow-up
- Build true multipart upload endpoint for resumes.
- Apply byte-level MIME detection (libmagic/signature approach).
- Add malware scan callback before persistence.
- Add structured security event metrics for rejected uploads (without logging raw file bytes/text).
