# Hosted Coaching App + Members Flow Threat Model

Last Updated: 2026-03-02  
Owner: Security Agent (Squarespace integration workstream)

## Scope
Threat model for the member journey described in `SQUARESPACE_INTEGRATION_IMPLEMENTATION_PLAN.md`:
1. Member purchases/accesses coaching on Squarespace.
2. Member launches hosted app (`coach.gambilldataengineering.com`).
3. App checks auth/session + subscription status.
4. Member performs intake/generation actions containing personal data.

In scope:
- Hosted app auth/session and subscription check endpoints
- Member launch token handoff risk
- Unauthorized route access and token misuse
- PII leakage risk in security/operational logs

Out of scope (tracked separately):
- Full Stripe webhook signature hardening
- Malware scanning pipeline for binary uploads
- Long-term IAM/SSO architecture

---

## Assets to Protect
- Coaching member access rights (paid-only experience)
- Session tokens and launch tokens
- Applicant PII (email, resume text, self-assessment text)
- Subscription status and plan metadata
- Operational logs and telemetry

---

## Trust Boundaries
1. **Public internet -> Squarespace member area**
2. **Squarespace member page -> hosted app launch URL**
3. **Hosted app frontend -> API (`/auth/*`, `/coaching/*`)**
4. **API -> persistence/logging systems**

The highest-risk boundary is #2 and #3 where token replay or unauthorized callers can attempt direct API access.

---

## Key Threats (STRIDE-oriented)

### 1) Spoofing / Unauthorized Access
- **Threat:** Non-member calls coaching endpoints directly.
- **Vectors:** Missing bearer token, malformed bearer format, low-privilege valid token.
- **Controls:**
  - Bearer token required by `get_current_session`/`get_current_user`
  - Role guard (`assert_role`) on coaching write/subscription endpoints
  - Regression tests for 401/403 behavior

### 2) Token Replay / Misuse
- **Threat:** Stolen or old token reused after logout/revocation.
- **Vectors:** Replay of previously valid bearer token.
- **Controls:**
  - Token revocation via `/auth/logout`
  - Session validation check on every protected request
  - Test confirms revoked token cannot access coaching routes

### 3) Information Disclosure (PII / secrets)
- **Threat:** Email, resume text, passwords, launch tokens leak into logs.
- **Vectors:** Naive logging of request bodies in auth/subscription/coaching flows.
- **Controls:**
  - PII-safe logging payload helpers (`pii_safe_*_log_payload`)
  - Metadata-only summaries (length/hits/hash) instead of raw content
  - Test coverage validates raw email/token/password are absent from captured logs

### 4) Tampering
- **Threat:** Caller manipulates subscription status payload to bypass gating.
- **Vectors:** Client-submitted status set to `active` without provider proof.
- **Current state:** Endpoint is an integration scaffold and does not trust external provider webhook yet.
- **Mitigation next:** Provider-signed webhook ingestion + server-owned status table, deny client-authoritative status writes.

### 5) Denial of Service
- **Threat:** High-rate auth/subscription calls to exhaust session map or API resources.
- **Current controls:** Session map cap exists.
- **Gap:** Route-level rate limiting not yet globally enforced.

---

## Security Test Mapping (implemented)
- `test_coaching_intake_requires_valid_bearer_token` -> blocks missing/malformed auth.
- `test_coaching_intake_blocks_reused_or_invalidated_token` -> blocks revoked-token replay.
- `test_coaching_subscription_status_denies_viewer_role` -> denies unauthorized role.
- `test_subscription_status_logging_masks_email_and_token` -> validates PII-safe logging on subscription endpoint.
- `test_auth_login_logging_never_includes_password` -> validates PII-safe logging on auth endpoint.

---

## Frontend Link Safety Policy (Pilot Baseline)
- Treat all LLM-produced links and user-supplied URLs as untrusted input.
- Frontend must only render navigation targets with `http://` or `https://` schemes.
- Frontend must reject or neutralize links using `javascript:`, `data:`, `file:`, or private/loopback hosts.
- Use `rel="noopener noreferrer"` on external links and avoid `dangerouslySetInnerHTML` for untrusted content.
- Never expose secrets/tokens/passwords in link text, query strings, or telemetry payloads.

## Backend + Frontend Defense-in-Depth
Security controls are intentionally layered so one bypass does not expose members or data:
- **Frontend controls**
  - URL rendering restrictions and safe-link UI behavior.
  - Clear user messaging when unsafe links are blocked.
- **Backend controls**
  - URL safety validation + fetch hardening in job-link processing.
  - Role guard + active-subscription checks on review/generation endpoints.
  - PII-safe logging to prevent sensitive payload leaks in observability paths.
- **Regression assurance**
  - API tests cover authz/subscription denials and unsafe content scrubbing.
  - Regenerate/quality-delta responses are verified to avoid leaking prior raw provider payloads.

## Residual Risk + Follow-ups
1. **Launch-token trust model not cryptographically enforced yet**
   - Add signed, short-TTL launch token with nonce/jti replay prevention.
2. **Session store is in-memory only**
   - Move to production JWT or persistent session store with rotation and revocation list.
3. **No centralized log-sanitizer middleware**
   - Add global logging filter to enforce masking invariants on all handlers.
4. **Subscription source-of-truth is still scaffolded**
   - Ingest provider webhook with signature verification and server-managed status.
5. **Rate limiting not complete on auth/subscription routes**
   - Add per-IP and per-account throttling.
