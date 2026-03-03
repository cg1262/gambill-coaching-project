# Sprint 4 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-03
Sprint Goal: Deterministic build stability + project quality upgrade + pilot-ready coach workflow.

## Checkpoint Update (2026-03-03 - Sprint 4 Backend Core Execution)

- Done:
  - Restored coach review queue backend reliability paths in `apps/api/main.py`:
    - added `POST /coaching/review/approve-send` (persists `approved_sent`, returns handoff launch token).
    - added `POST /coaching/member/launch-token/verify` (HMAC-backed workspace/submission binding check).
  - Restored subscription lifecycle reliability endpoints/contracts:
    - added import + usage of `get_coaching_subscription_event` and `list_recent_coaching_subscription_events`.
    - added `GET /coaching/subscription/lifecycle-readiness` with consistency checks.
    - hardened `POST /coaching/subscription/sync` idempotency (provider event replay detection via raw_event.id) and explicit `idempotent_replay` response field.
  - Upgraded Project Output Quality v3 logic in `apps/api/coaching.py`:
    - added milestone specificity scoring (`milestone_specificity_score`) to quality computation.
    - expanded diagnostics with targeted regeneration hints, recommended-regeneration signal, and richer deficiency metadata.
  - Added deterministic API pytest config in `apps/api/pytest.ini` (`pythonpath=.` + `testpaths=tests`).

- Validation:
  - Existing venv (`apps/api/.venv`):
    - `.venv\\Scripts\\python -m pytest` ✅ `101 passed, 4 skipped, 1 warning in 8.19s`
  - Clean venv (`repo/.venv-ci`):
    - `.venv-ci\\Scripts\\python.exe -m pip install -r apps/api/requirements.txt` ✅
    - `..\\..\\.venv-ci\\Scripts\\python.exe -m pytest` (from `apps/api`) ✅ `101 passed, 4 skipped, 1 warning in 20.15s`

- Risks:
  - Launch token flow is stateless HMAC verification (no one-time-use/jti replay store yet).

- Needs from others:
  - Product/security decision on whether to require strict launch-token TTL + one-time redemption before pilot hardening sign-off.

- Next:
  1. Add optional launch-token TTL + replay nonce persistence for high-assurance member handoff.
  2. Add targeted tests asserting new quality diagnostics hints on low-quality outputs.
  3. Keep lifecycle-readiness endpoint in pilot runbook checks.

## Checkpoint Update (2026-03-03 - Security Pilot Gate Pass)

- Done:
  - Verified generic 401/403 denial contract coverage across additional protected coaching routes (`/coaching/health/readiness`, `/coaching/intake/submissions`, `/coaching/sow/generate-draft`) and kept contract stable (`ok`, `code`, `auth_required`, `subscription_required`, `message`).
  - Expanded security regression coverage for stale auth-state recovery + auth contract consistency:
    - added/expanded tests in `apps/api/tests/test_auth_contract_security.py`.
    - aligned stale/legacy expectation in `apps/api/tests/test_coaching_security_access.py` to the active generic denial contract.
  - Hardened generated narrative secret masking:
    - `sanitize_generated_sow(...)` now recursively masks secret-like strings inside structured `project_story` objects (not just string-form narratives).
  - Expanded link/url defense-in-depth regression tests:
    - added parametrized blocking checks for unsafe resource URLs (`127.0.0.1`, credentialed localhost, `data:`, `javascript:`) in `apps/api/tests/test_llm_output_security.py`.
  - Added secret/provider leakage checks for new diagnostics surfaces:
    - validated `quality.quality_diagnostics` remains free of provider payload/keys.

- Validation:
  - `python -m pytest -q tests/test_auth_contract_security.py tests/test_llm_output_security.py` ✅ (16 passed)
  - `python -m pytest -q tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py` ✅ (25 passed)

- Risks:
  - Frontend-specific stale-auth UX still relies on integration behavior; no dedicated web unit/E2E harness is in this pass.
  - URL safety remains browser/backend layered; backend is authoritative for block/strip, frontend should continue treating URLs as untrusted display data.

- Needs from others:
  - Product/ops confirmation of go/no-go threshold interpretation for open items in pilot checklist (webhook signature enforcement and route rate limiting remain open).

- Next:
  1. Add pilot gate sign-off row with commit SHA once merged.
  2. Extend frontend regression harness for stale-banner clearing behavior.
  3. Close remaining checklist blockers (provider signature verification, route rate limiting).

## Checkpoint Update (2026-03-03 - Frontend Stability + Intake/Diagnostics Completion Pass)

- Done:
  - Upgraded `apps/web/scripts/build-clean.ps1` for deterministic recovery:
    - enforces lockfile presence (`package-lock.json`) before recovery.
    - prints Node/npm version guidance for reproducible environments.
    - expands recoverable-failure detection to include missing local `tsc`/`next` module cases (not only `EISDIR`).
    - switches recovery reinstall path to `npm ci --no-audit --no-fund` for lockfile-true installs.
  - Extended `CoachingProjectWorkbench` quality diagnostics panel:
    - now surfaces `structure_score`, `section_order_valid`, and explicit `missing_sections` list.
    - adds actionable regenerate guidance derived from diagnostics (missing sections, order mismatch, deficiency count, low band).
  - Preserved/validated intake UX completion elements in active form implementation:
    - labeled skill confidence rows.
    - tools/platform checklists with `Other` handling in exposure section.
    - clear constraints/support labels and helper copy.
  - Preserved stale auth/readiness error clearing path using centralized `markAuthenticatedApiSuccess()` / `clearAuthStaleState()` on successful protected calls.

- Validation:
  - pending local execution in this pass:
    - `npm run typecheck` (from `apps/web`)
    - `npm run build:clean` (from `apps/web`)

- Risks:
  - Build stability still depends on local host filesystem/package extraction health; script now narrows recovery but cannot fully remediate host-level npm/tar extraction faults.
  - `preferences` step remains separate from self-assessment exposure checklist semantics; future UX may unify these if product wants a single source of truth.

- Needs from others:
  - Product confirmation on whether preference-stage platform/tool selectors also require explicit `Other` free-text fields.
  - Ops confirmation of pinned Node/npm matrix for CI and developer onboarding docs.

- Next:
  1. Run web typecheck/build-clean on stable disk context and capture output in checkpoint docs.
  2. Add frontend regression tests for diagnostics guidance rendering.
  3. Add build script note to README/web setup docs if this becomes the default recovery path.

## Epic A — Deterministic Build & Environment Stability (P0)

### A1. Web deterministic clean build
- Owner: Frontend + Security
- Scope:
  - eliminate recurring `EISDIR` / missing `tsc` / missing `next` local instability
  - add deterministic install/build script with lockfile validation
  - document exact Node/npm versions and one-command recovery
- Acceptance:
  - fresh clone + scripted setup yields passing `npm run typecheck` and `npm run build` twice in a row

### A2. API test determinism
- Owner: Backend
- Scope:
  - pin/validate runtime dependencies (`httpx` + test deps)
  - ensure full API suite runs green from clean venv
- Acceptance:
  - full `pytest -q` passes in clean venv with documented setup

## Epic B — Project Output Quality v3 (P0)

### B1. Exemplar-aligned project narrative quality
- Owner: Backend
- Scope:
  - enforce project section depth using reference structure from user examples
  - strengthen milestone specificity and business rationale quality gates
  - improve diagnostics for low-quality sections and regeneration hints
- Acceptance:
  - generated outputs consistently include robust sections and actionable depth

### B2. Frontend quality visibility
- Owner: Frontend
- Scope:
  - clearly render quality/structure diagnostics and missing-section prompts
  - guide regeneration with explicit user-facing recommendations
- Acceptance:
  - coach can quickly identify weak outputs and trigger targeted regeneration

## Epic C — Intake UX Completion (P1)

### C1. Self-assessment final polish
- Owner: Frontend
- Scope:
  - ensure labeled skills confidence fields are unambiguous
  - finalize tools/platform checklists with `Other` handling
  - clarify constraints/support semantics and helper copy
- Acceptance:
  - first-time user can complete intake without clarification questions

### C2. Session/auth UX resilience
- Owner: Frontend + Backend + Security
- Scope:
  - guarantee stale session banner and readiness state never persist after successful auth calls
  - add end-to-end regression checks
- Acceptance:
  - no sticky auth/readiness error state in validated smoke flow

## Epic D — Coach Workflow Pilot Closeout (P1)

### D1. Review queue and actions reliability
- Owner: Frontend + Backend
- Scope:
  - confirm notes/status save + approve/send behavior and filtering persistence
- Acceptance:
  - coach can process queue end-to-end without refresh inconsistencies

### D2. Pilot release checklist and handoff
- Owner: Security + Orchestrator
- Scope:
  - consolidate test evidence, risk list, and go/no-go checklist
- Acceptance:
  - single pilot readiness report with explicit blockers/non-blockers

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
