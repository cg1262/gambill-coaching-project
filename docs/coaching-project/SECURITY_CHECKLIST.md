# Coaching Project Security Checklist (Baseline)

Last Updated: 2026-03-01
Owner: Security Agent

## Scope
Baseline controls for coaching project creation flow covering:
1. File handling guards
2. Secret/auth handling and masking checks
3. PII/privacy-aware logging/export behavior

---

## 1) File Handling Guards (Resume Intake)
Reference: `docs/coaching-project/FILE_UPLOAD_THREAT_GUARD.md`
- [x] Restrict resume file extensions to approved list (`.pdf`, `.doc`, `.docx`, `.txt`).
- [x] Restrict accepted content types to expected resume document MIME types.
- [x] Enforce maximum upload size (`5 MB` baseline).
- [x] Reject empty files.
- [x] Normalize filename using basename to drop traversal/path fragments.
- [x] Build storage path from sanitized workspace + filename under controlled base directory.
- [ ] Add server-side MIME sniffing for uploaded bytes (future hardening).
- [ ] Add malware scanning hook before persistence (future hardening).

## 2) Secrets/Auth Hardening (Baseline)
- [x] Keep RBAC checks on coaching intake validation endpoint (`admin`/`editor`).
- [x] Ensure sensitive connection settings are masked when returned by APIs.
- [x] Mask common secret patterns in text payloads before logs/exports (`token`, `password`, `client_secret`, `api_key`, bearer tokens).
- [ ] Remove local `admin/admin123` fallback in production profile.
- [ ] Move session/token storage from in-memory to persistent signed/JWT lifecycle (production).

## 3) PII/Privacy Controls (Baseline)
- [x] Add PII hit detection helper for `email`, `ssn`, and `phone` checks.
- [x] Add secret masking utility for nested payloads and free-form text.
- [x] Add security-focused baseline tests for file validation and masking behavior.
- [ ] Enforce masking on all export/report endpoints via shared utility wrapper.
- [ ] Add data retention policy + delete workflow for uploaded resumes.

## 4) Regression Test Stubs Added
- `apps/api/tests/test_security_regression_stubs.py`
  - resume upload polyglot rejection (stub)
  - malicious content-type upload rejection (stub)
  - oversize upload rejection (stub)
  - export/log masking regression (stub)

## 5) Affiliate/Trust Language in Generated Outputs
- [x] Include affiliate disclosure language in generated `resource_plan.affiliate_disclosure`.
- [x] Include trust-language in `resource_plan.trust_language` and `mentoring_cta.trust_language`.
- [x] Validate disclosure/trust fields in SOW validation loop (`AFFILIATE_DISCLOSURE_MISSING`, `TRUST_LANGUAGE_MISSING`).

## 6) Immediate Follow-ups (Next Sprint)
1. Implement true multipart upload endpoint with byte-level validation.
2. Add centralized logging filter/middleware for secret masking.
3. Add end-to-end test to prove uploaded resume never appears in logs/raw exports.
