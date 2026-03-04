# Sprint 8 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-04
Sprint Goal: Permanent runtime stability + frontend review readiness + pilot hardening closeout.

## Epic A — Permanent Runtime Policy (P0)

### A1. Project-level runtime pinning
- Owner: Frontend + Security
- Status: ✅ Completed
- Scope delivered:
  - Verified runtime contract remains pinned in `apps/web/package.json` (`engines`, `volta`, `packageManager`).
  - Confirmed `.nvmrc` alignment to Node `20.11.1`.
  - Preserved fail-fast runtime gate (`scripts/require-runtime.cjs`) for Node `>=20.11.1 <21` and npm `10.x`.

### A2. Deterministic install/build policy
- Owner: Frontend
- Status: ⚠️ Partially complete (policy gate enforced; compliant-runtime green build proof still pending)
- Scope delivered:
  - Runtime gate remains enforced before `dev`, `typecheck`, `build`, and `build:clean`.
  - Added executable runtime policy regression tests in `apps/web/scripts/require-runtime.test.cjs`.
  - Added npm script `runtime:test` for repeatable policy verification.

## Epic B — Frontend Review Readiness (P0)

### B1. Review pass polish
- Owner: Frontend
- Status: ↔ No change in this security pass

### B2. Build blocker resolution evidence
- Owner: Frontend + Security
- Status: ✅ Evidence refreshed
- Evidence:
  - Host runtime remains out of contract (`Node v24.13.1`, `npm 11.8.0`).
  - `npm run typecheck` now fails fast at runtime gate (expected).
  - `npm run build:clean` now fails fast at runtime gate (expected).

## Epic C — Security & Pilot Gate (P1)

### C1. Runtime policy security posture
- Owner: Security
- Status: ✅ Completed for Sprint 8 scope
- Scope delivered:
  - Reviewed permanent runtime enforcement behavior and remediation messaging.
  - Refactored `apps/web/scripts/require-runtime.cjs` for testability and explicit runtime detection helpers.
  - Added output redaction helper for secret-like patterns in runtime diagnostic strings.
  - Added regression coverage for:
    - semver parsing and runtime pass/fail behavior,
    - npm/node major policy enforcement,
    - secret-like token redaction,
    - failure-path message sanitization.

### C2. Pilot hardening updates
- Owner: Security + Backend
- Status: ✅ Updated with latest Sprint 8 evidence

## Epic D — Backend Supportive Stabilization (P1)

### D1. Config/admin hooks continuity
- Owner: Backend
- Status: ✅ Revalidated (no regressions observed in security pack)

## Required Reporting Format
- **Done:**
  - Added runtime policy regression suite (`apps/web/scripts/require-runtime.test.cjs`).
  - Added runtime diagnostics redaction and testable runtime check internals (`apps/web/scripts/require-runtime.cjs`).
  - Added npm script: `runtime:test`.
  - Re-ran security regression packs + API compile checks.
  - Refreshed pilot hardening + POC status docs with Sprint 8 evidence.

- **Validation:**
  - `npm run runtime:test` (apps/web) → **pass** (4 tests).
  - `npm run typecheck` (apps/web) → **expected fail-fast** on runtime mismatch (`Node v24.13.1`, `npm 11.8.0`).
  - `npm run build:clean` (apps/web) → **expected fail-fast** on runtime mismatch.
  - `python -m pytest tests/test_auth_contract_security.py tests/test_llm_output_security.py tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_subscription.py` (apps/api) → **52 passed, 1 warning**.
  - `python -m pytest -q tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py` (apps/api) → **pass** (14 tests), 1 warning.
  - `python -m compileall -q .` (apps/api) → **pass**.

- **Risks:**
  - Deterministic successful web build proof under compliant runtime (Node 20.11.1 + npm 10.x) is still pending on this host.
  - Invalid webhook signature alerting remains an ops follow-up blocker from prior sprint gates.

- **Needs from others:**
  - Platform/runtime owner to provide compliant Node/npm runtime on host or CI runner for final deterministic build proof.
  - Ops owner to wire alerting for repeated invalid webhook signatures.

- **Next:**
  1. Run `npm ci --no-audit --no-fund && npm run typecheck && npm run build && npm run build` on compliant runtime and attach logs.
  2. Keep `runtime:test` in pre-release validation checklist.
  3. Close alerting follow-up and move pilot gate from conditional to full GO.