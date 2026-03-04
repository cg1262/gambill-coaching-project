# Coaching Project Security Checklist (Baseline)

Last Updated: 2026-03-04
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
- [x] Mask secret-like filename tokens in resume validation response echoes (`validation.filename`, `safe_storage_path`, and error message text).
- [ ] Add server-side MIME sniffing for uploaded bytes (future hardening).
- [ ] Add malware scanning hook before persistence (future hardening).

## 2) Secrets/Auth Hardening (Baseline)
- [x] Keep RBAC checks on coaching intake validation endpoint (`admin`/`editor`).
- [x] Enforce route-level rate limiting on coaching resume validation endpoint via subscription policy.
- [x] Add authz contract tests for resume validation endpoint (401 unauth + 403 viewer role denial).
- [x] Ensure sensitive connection settings are masked when returned by APIs.
- [x] Mask common secret patterns in text payloads before logs/exports (`token`, `password`, `client_secret`, `api_key`, bearer tokens).
- [ ] Remove local `admin/admin123` fallback in production profile.
- [ ] Move session/token storage from in-memory to persistent signed/JWT lifecycle (production).

## 3) Form Input Validation Controls (Coaching Intake)
Reference: `docs/coaching-project/FORM_INPUT_VALIDATION_POLICY.md`
- [x] Enforce strict payload shape (`extra=forbid`) on intake request model.
- [x] Restrict structured `preferences` fields to approved keys and typed bounds.
- [x] Enforce safe URL schemes (`http`/`https`) and fully-qualified host for `job_links`.
- [x] Bound freeform intake text lengths (`resume_text`, `self_assessment_text`).
- [x] Add API regression coverage for malformed job-link payloads and oversized freeform fields.

## 4) PII/Privacy Controls (Baseline)
- [x] Add PII hit detection helper for `email`, `ssn`, and `phone` checks.
- [x] Add secret masking utility for nested payloads and free-form text.
- [x] Add security-focused baseline tests for file validation and masking behavior.
- [ ] Enforce masking on all export/report endpoints via shared utility wrapper.
- [ ] Add data retention policy + delete workflow for uploaded resumes.

## 5) Regression Test Stubs Added
- `apps/api/tests/test_security_regression_stubs.py`
  - resume upload polyglot rejection (stub)
  - malicious content-type upload rejection (stub)
  - oversize upload rejection (stub)
  - export/log masking regression (stub)

## 6) Affiliate/Trust Language in Generated Outputs
- [x] Include affiliate disclosure language in generated `resource_plan.affiliate_disclosure`.
- [x] Include trust-language in `resource_plan.trust_language` and `mentoring_cta.trust_language`.
- [x] Validate disclosure/trust fields in SOW validation loop (`AFFILIATE_DISCLOSURE_MISSING`, `TRUST_LANGUAGE_MISSING`).

## 7) LLM Integration + Generated Output Hardening
- [x] Add missing-key guardrail for probabilistic/LLM-backed validation path (`LLM_API_KEY_MISSING` finding instead of crash).
- [x] Ensure probabilistic impact path fails safe when no LLM key exists (empty dependencies, no exception).
- [x] Add generated output URL sanitizer for SOW links and mentoring program URLs.
- [x] Block dangerous URL schemes (`javascript:`, `data:`) and flag with `UNSAFE_*` findings.
- [x] Mask secret-like text patterns in generated resource and mentoring narrative before response/export.
- [x] Add regression tests proving unsafe URLs are blocked/flagged and secret-like strings are absent from response payloads.
- [x] Validate default project charter milestone sections still pass no-leak and safe-URL checks after sanitization.

## 8) Immediate Follow-ups (Next Sprint)
1. Implement true multipart upload endpoint with byte-level validation.
2. Add centralized logging filter/middleware for secret masking.
3. Add end-to-end test to prove uploaded resume never appears in logs/raw exports.
4. Replace placeholder probabilistic engine with real LLM client + strict structured output schema validation.

## 9) Sprint 3 Security Execution (Regression + Defense-in-Depth)
- [x] Verified generic denial contract (`ok`, `code`, `auth_required`, `subscription_required`, `message`) across auth + coaching 401/403 routes.
- [x] Added regression for role-based 403 and subscription-based 403 without leaking internal denial details.
- [x] Tightened frontend link rendering policy for blocked private hosts (`localhost`, `::1`, RFC1918 IPv4 ranges, `.local`) to match backend unsafe URL policy intent.
- [x] Expanded backend URL safety regression checks for private IPv4 and IPv6 loopback URL fetch blocking.
- [x] Expanded generated-output sanitization to mask secret-like values in project title/story, business outcome narrative, milestone execution plan, expected deliverable, and business rationale fields.

### CI-ready security regression command pack
Run from `apps/api`:
- `python -m pytest -q tests/test_auth_contract_security.py`
- `python -m pytest -q tests/test_security_baseline.py`
- `python -m pytest -q tests/test_security_sprint2.py::test_e2_fetch_job_text_blocks_unsafe_urls`
- `python -m pytest -q tests/test_llm_output_security.py`
- `python -m pytest -q tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_llm_contract.py`

Optional full pass:
- `python -m pytest -q tests/test_auth_contract_security.py tests/test_security_sprint2.py tests/test_llm_output_security.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_llm_contract.py`
