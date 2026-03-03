# Pilot Release Hardening Checklist (Coaching Project)

Use this as a go/no-go gate before enabling pilot users.

## Current Gate Status (2026-03-03)
- **Security pilot gate:** CONDITIONAL GO
- **Why conditional:** auth/session contract, URL hardening, and secret-masking regressions are passing; production blockers remain open in webhook signature verification and route-level rate limiting.

## 1) Auth + Subscription Enforcement
- [x] Verify all coaching generation routes require authenticated session + allowed role (`admin`/`editor`).
- [x] Verify inactive or missing subscription returns `403` on generation routes.
- [ ] Verify subscription status source of truth is server-side persisted state (not client-authoritative input).

## 2) Logging + Secret Hygiene
- [ ] Confirm auth/subscription logs only emit `pii_safe_*_log_payload` summaries.
- [ ] Confirm no raw secrets in logs (`password`, bearer/API tokens, client secrets, webhook signatures).
- [ ] Confirm no raw PII in logs (full email, resume text, self-assessment bodies, launch tokens).

## 3) Webhook + Provider Integrity
- [ ] Enforce webhook signature verification (Squarespace/Stripe) before mutating subscription state.
- [ ] Idempotently handle duplicate provider events (`event_id` replay-safe).
- [ ] Alert on repeated invalid signature attempts.

## 4) Abuse + Reliability Controls
- [ ] Apply route-level rate limits for `/auth/*` and subscription sync/status endpoints.
- [ ] Confirm token/session revocation works immediately for protected routes.
- [ ] Confirm safe failure behavior when Lakebase/provider dependencies are unavailable.

## 5) LLM Integration + Output Safety
- [x] Ensure LLM API key is loaded only from env/secret manager and never returned in API responses.
- [x] Verify missing LLM API key behavior is explicit and safe (no crash, no secret leak, deterministic fallback message/finding).
- [x] Ensure generated links are URL-sanitized before render/export (block `javascript:` and `data:` schemes).
- [x] Ensure generated narrative/resource text is secret-masked before persistence/export.

## 6) Test + Release Evidence
- [x] Run API security regression tests (auth, RBAC, inactive-subscription denial, logging masks, LLM guardrails).
- [ ] Run compile/build checks for API + web.
- [ ] Attach test/build output + commit SHA to pilot launch notes.

### Evidence Commands (2026-03-03 Security Pilot Gate)
- `python -m pytest -q tests/test_auth_contract_security.py tests/test_llm_output_security.py`
- `python -m pytest -q tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py`
