# Pilot Release Hardening Checklist (Coaching Project)

Use this as a go/no-go gate before enabling pilot users.

## Current Gate Status (2026-03-04)
- **Security pilot gate:** CONDITIONAL GO
- **Why conditional:** Sprint 8 security pass reconfirmed auth/session denial contract stability, instrumentation/event payload sanitization, generated-output URL safety, diagnostics secrecy, subscription replay safety, webhook signature/timestamp rejection behavior, and route-level throttling for auth + subscription status/sync/webhook surfaces. Runtime policy now has dedicated regression coverage (including secret-like output redaction checks), but pilot remains conditional on (1) deterministic web build success proof under compliant runtime (`Node 20.11.1`, `npm 10.x`) and (2) production alerting for repeated invalid webhook signatures.

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
- [ ] Alert on repeated invalid signature attempts.

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
- [ ] Run compile/build checks for API + web. *(API compile passes; on this host, web `typecheck`/`build:clean` are intentionally fail-fast due runtime mismatch (`Node v24.13.1`, `npm 11.8.0`) before build execution. Compliant-runtime green proof is still pending.)*
- [ ] Attach test/build output + commit SHA to pilot launch notes.

### Evidence Commands (2026-03-04 Security Pilot Gate Refresh)
- `python -m pytest tests/test_auth_contract_security.py tests/test_llm_output_security.py tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_subscription.py` → **52 passed, 1 warning**
- `python -m pytest -q tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py` → **14 passed, 1 warning**
- `python -m compileall -q .` → **pass**
- `npm run runtime:test` → **pass** (4 tests)
- `npm run typecheck` → **expected fail-fast** on runtime mismatch (`Node v24.13.1`, `npm 11.8.0`)
- `npm run build:clean` → **expected fail-fast** on runtime mismatch (`Node v24.13.1`, `npm 11.8.0`)
