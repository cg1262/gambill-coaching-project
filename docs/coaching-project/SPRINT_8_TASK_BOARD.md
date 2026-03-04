# Sprint 8 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-03
Sprint Goal: Permanent runtime stability + frontend review readiness + pilot hardening closeout.

## Checkpoint Update (2026-03-03 - Sprint 8 Backend Execution: Runtime/Rate-Limit Admin Config Contract Alignment)

### Done
- Added backend admin config surface to align with frontend runtime + rate-limit scaffolding:
  - `GET /admin/security/runtime-rate-limit-config`
  - `PUT /admin/security/runtime-rate-limit-config`
- Added new backend policy module:
  - `apps/api/admin_runtime_config.py`
  - exposes admin-editable snapshot/update contract for:
    - `web_runtime` (Node/npm policy + preflight script contract metadata)
    - `rate_limit_ui` (fallback retry seconds + helper message used by frontend internal admin scaffold)
  - includes camelCase aliases (`defaultRetrySeconds`, `helperMessage`) for frontend contract continuity.
- Extended frontend API client contract for new admin config endpoint:
  - `apps/web/src/lib/api.ts`
  - added typed `AdminRuntimeRateLimitConfigResult`
  - added `adminRuntimeRateLimitConfig()` and `saveAdminRuntimeRateLimitConfig(...)` methods.
- Added Sprint 8 backend regression coverage:
  - `apps/api/tests/test_coaching_sprint8_backend.py`
  - validates endpoint availability, required schema fields, and update roundtrip behavior.

### Validation
- Focused backend regression run (`apps/api`):
  - `python -m pytest -q tests/test_coaching_sprint8_backend.py tests/test_coaching_sprint7_backend.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py`
  - Result: **18 passed, 1 warning**.
- Full backend suite (`apps/api`):
  - `python -m pytest -q`
  - Result: **128 passed, 4 skipped, 1 warning**.

### Risks
- Runtime/rate-limit admin config is intentionally in-memory + env-default backed (`source: in_memory_with_env_defaults`), not yet persisted per workspace.
- Frontend internal admin panel currently still saves localStorage directly; API wiring is now available but not yet bound to UI controls.

### Needs from others
- Frontend pass to wire internal admin panel to `GET|PUT /admin/security/runtime-rate-limit-config` and define role-gated UX rollout.

### Next
1. Decide whether runtime/rate-limit admin config should become workspace-scoped persisted state.
2. Wire frontend internal admin panel to new backend contract with optimistic save + fetch-on-load behavior.
3. Add audit trail if policy/admin config changes need historical traceability.

## Epic A — Permanent Runtime Policy (P0)

### A1. Project-level runtime pinning
- Owner: Frontend + Security
- Scope:
  - Add/verify `packageManager` pin in `apps/web/package.json`
  - Keep `.nvmrc` aligned with Node 20.11.1
  - Add Volta pinning metadata and docs
- Acceptance:
  - Entering `apps/web` auto-resolves expected runtime path (or fails with exact remediation)

### A2. Deterministic install/build policy
- Owner: Frontend
- Scope:
  - enforce `npm ci` workflow in docs/scripts
  - strengthen recovery script and preflight checks
- Acceptance:
  - repeatable: `npm ci`, `npm run typecheck`, `npm run build` in clean env

## Epic B — Frontend Review Readiness (P0)

### B1. Review pass polish
- Owner: Frontend
- Scope:
  - verify and fix remaining UX issues in coaching flow:
    - session banner clearing
    - self-assessment labels/clarity
    - tools/platform checkbox behavior
    - constraints/support wording
    - diagnostics and regenerate guidance presentation
- Acceptance:
  - user review-ready build with clear issue panel and no stale auth state

### B2. Build blocker resolution evidence
- Owner: Frontend + Security
- Scope:
  - produce command evidence for runtime parity and build outcomes
- Acceptance:
  - evidence captured in docs with blocker/non-blocker status

## Epic C — Security & Pilot Gate (P1)

### C1. Runtime policy security posture
- Owner: Security
- Scope:
  - ensure runtime/version enforcement and override paths do not weaken controls
  - verify no sensitive leakage in runtime/build errors
- Acceptance:
  - regression checks pass and checklist updated

### C2. Pilot hardening updates
- Owner: Security + Backend
- Scope:
  - refresh pilot hardening checklist with current status and pending blockers
- Acceptance:
  - explicit GO/CONDITIONAL GO recommendation with rationale

## Epic D — Backend Supportive Stabilization (P1)

### D1. Config/admin hooks continuity
- Owner: Backend
- Scope:
  - ensure rate-limit/webhook/runtime config surfaces remain coherent with frontend admin scaffolding
- Acceptance:
  - backend/frontend config contract documented and validated

## Checkpoint Update (2026-03-03 - Sprint 8 Frontend Execution: Runtime Policy + Review Readiness)

- Done:
  - Runtime policy made permanent in `apps/web`:
    - kept `.nvmrc` pinned to `20.11.1`
    - aligned `packageManager` (`npm@10.8.2`) + `engines`
    - added explicit Volta pin metadata in `apps/web/package.json`:
      - `volta.node=20.11.1`
      - `volta.npm=10.8.2`
  - Hardened deterministic command workflow:
    - added `npm run install:ci` (`npm ci --no-audit --no-fund`)
    - added `npm run verify:deterministic` (install/typecheck/build/build)
    - retained runtime fail-fast guard on `dev/typecheck/build/build:clean`
    - kept actionable remediation path in runtime/build scripts and docs.
  - Updated `apps/web/README.md` with:
    - Volta + `.nvmrc` + package manager alignment
    - first-class deterministic flow command
    - explicit runtime remediation sequence.
  - Confirmed coaching UX review items remain addressed in `CoachingProjectWorkbench`:
    - stale session banner clearing uses centralized auth stale-state clear + protected-call success resets
    - self-assessment confidence controls have explicit field labels
    - tools/platform exposure uses checkbox UX with `Other` toggles + conditional inputs
    - constraints/support section includes concrete guidance and labeled fields
    - diagnostics panel includes deficiency lists and regenerate guidance.

- Validation:
  - From `apps/web` under host runtime Node `v24.13.1`, npm `11.8.0`:
    - `npm run runtime:check` -> **failed as expected** with explicit parity/remediation output.
    - `npm run typecheck` -> **failed fast as expected** via `pretypecheck` runtime gate.
    - `npm run build` -> **failed fast as expected** via `prebuild` runtime gate.
    - `npm run build:clean` -> **failed fast as expected** via `prebuild:clean` runtime gate.
  - Runtime gate output confirms required baseline:
    - Node `>=20.11.1 <21`
    - npm `10.x`.

- Risks:
  - Deterministic green proof (`typecheck/build/build:clean` pass) remains blocked on this host until execution under compliant runtime (Node `20.11.1` + npm `10.x`).

- Needs from others:
  - Compliant runtime execution window (or CI runner pinned to Node 20.11.1 + npm 10.x) for final green evidence capture.

- Next:
  1. Run `npm run verify:deterministic` under compliant runtime and capture pass output.
  2. Run `npm run build:clean` under compliant runtime and capture pass output.
  3. Mark Sprint 8 frontend gate fully green after compliant evidence is attached.

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
