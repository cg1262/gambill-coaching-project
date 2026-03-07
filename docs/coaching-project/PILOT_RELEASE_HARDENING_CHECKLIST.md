# Pilot Release Hardening Checklist (Coaching Project)

Use this as a go/no-go gate before enabling pilot users.

## Current Gate Status (2026-03-07, Sprint 16 security checkpoint)
- **Security pilot gate:** CONDITIONAL GO
- **Why conditional:** Sprint 16 security revalidation confirms auth/session/rate-limit/webhook controls remain intact, invalid-signature alert routing remains operational for configured webhook delivery, and diagnostics/runtime error outputs remain secret-safe under regression coverage. Blocking dependency remains deterministic compliant-runtime web compile/build proof (`Node 20.11.1`, `npm 10.x`) plus Next.js advisory remediation closure.

## 1) Auth + Subscription Enforcement
- [x] Verify all coaching generation routes require authenticated session + allowed role (`admin`/`editor`).
- [x] Verify inactive or missing subscription returns `403` on generation routes.
- [ ] Verify subscription status source of truth is server-side persisted state (not client-authoritative input).

## 2) Logging + Secret Hygiene
- [ ] Confirm auth/subscription logs only emit `pii_safe_*_log_payload` summaries.
- [x] Confirm no raw secrets in logs (`password`, bearer/API tokens, client secrets, webhook signatures). *(Regression-backed via `test_security_rate_limit_webhook.py::test_no_sensitive_leak_in_webhook_rejection_logs`.)*
- [x] Confirm runtime/build mismatch diagnostics do not echo secret-like token material in failure output. *(Regression-backed via `apps/web/scripts/require-runtime.test.cjs`.)*
- [ ] Confirm no raw PII in logs (full email, resume text, self-assessment bodies, launch tokens).

## 3) Webhook + Provider Integrity
- [x] Enforce webhook signature verification (Squarespace/Stripe) before mutating subscription state. *(When webhook secret is configured.)*
- [x] Idempotently handle duplicate provider events (`event_id` replay-safe).
- [x] Alert on repeated invalid signature attempts. *(`_record_invalid_webhook_signature_attempt(...)` emits `coaching_webhook_invalid_signature_alert` at configurable threshold/window, persists recent alerts for ops visibility, and supports best-effort routed delivery when `WEBHOOK_INVALID_SIG_ALERT_WEBHOOK_URL` is configured; covered by `test_invalid_signature_alert_emits_after_threshold_sync`, `test_invalid_signature_alert_emits_after_threshold_webhook`, and `test_invalid_signature_alert_routes_to_configured_webhook`.)*

## 4) Abuse + Reliability Controls
- [x] Apply route-level rate limits for `/auth/*` and subscription sync/status/webhook endpoints. *(Enforced via `subscription` policy and generic 429 contract regressions.)*
- [ ] Confirm token/session revocation works immediately for protected routes.
- [ ] Confirm safe failure behavior when Lakebase/provider dependencies are unavailable.
- [x] Validate override model auditability for throttling policy changes. *(Admin snapshot/update endpoints: `GET|PUT /admin/security/rate-limits`; env override knobs documented in `apps/api/rate_limits.py`.)*

## 5) LLM Integration + Output Safety
- [x] Ensure LLM API key is loaded only from env/secret manager and never returned in API responses.
- [x] Verify missing LLM API key behavior is explicit and safe (no crash, no secret leak, deterministic fallback message/finding).
- [x] Ensure generated links are URL-sanitized before render/export (block `javascript:` and `data:` schemes).
- [x] Ensure generated narrative/resource text is secret-masked before persistence/export.

## 6) Test + Release Evidence
- [x] Run API security regression tests (auth, RBAC, inactive-subscription denial, logging masks, LLM guardrails).
- [ ] Run compile/build checks for API + web. *(API compile passes. Web remains blocked pending deterministic runner hygiene: host runtime gate intentionally fails (`Node v24.13.1`, `npm 11.8.0`), and compliant-runtime attempt (`Volta Node 20.11.1/npm 10.8.2`) still hit local filesystem/install instability (`npm ci` EPERM unlink in `node_modules`).)*
- [ ] Attach test/build output + commit SHA to pilot launch notes.

### Evidence Commands (2026-03-07 Sprint 16 Security Revalidation)
- `python -m pytest tests/test_auth_contract_security.py tests/test_auth_sessions.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py tests/test_llm_output_security.py` (apps/api) → **43 passed, 1 warning**
- `python -m pytest -q tests/test_security_rate_limit_webhook.py::test_invalid_signature_alert_routes_to_configured_webhook` (apps/api) → **pass**
- `python -m py_compile main.py webhook_security.py webhook_alerts.py coaching\sow_validation.py coaching\sow_security.py` (apps/api) → **pass**
- `node --test scripts/require-runtime.test.cjs` (apps/web) → **5 passed**
- `npm audit --omit=dev --json` (apps/web) → **1 high vulnerability (`next`)**; advisories include `GHSA-h25m-26qc-wcjf` and `GHSA-9g9p-9gw9-jx7f`; current lockfile fix path remains major (`next@16.1.6`), tracked in `docs/coaching-project/NEXTJS_VULNERABILITY_REMEDIATION_PLAN.md`.
- Full command output: `docs/coaching-project/evidence/sprint16-security-checkpoint.log`.
