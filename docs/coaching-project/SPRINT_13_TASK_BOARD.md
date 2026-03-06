# Sprint 13 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-06
Sprint Goal: Stabilize deterministic web builds, improve project output quality fidelity, and strengthen conversion + coach workflow loops.

## Epic A — Deterministic Build & Runtime Stability (P0)

### A1. Windows build corruption blocker closeout
- Owner: Frontend + Security
- Scope:
  - isolate and resolve persistent `EISDIR` / `EPERM` corruption signatures
  - harden `build-clean`/deterministic scripts for repeatability
- Acceptance:
  - two consecutive successful runs under compliant runtime:
    - `npm ci`
    - `npm run typecheck`
    - `npm run build`

### A2. Known-good startup mode
- Owner: Frontend
- Scope:
  - enforce Volta/runtime parity and one-command startup path
  - improve startup diagnostics/remediation guidance
- Acceptance:
  - startup script reaches healthy web+api in a clean shell without manual intervention

## Epic B — Output Quality Fidelity v5 (P0)

### B1. Golden output snapshot tests
- Owner: Backend
- Scope:
  - add 3–5 golden project outputs aligned to anchor style/structure
  - fail CI on major structural/tone/depth drift
- Acceptance:
  - golden suite passes with zero major-deficiency codes

### B2. Stronger deficiency-aware regeneration
- Owner: Backend + Frontend
- Scope:
  - tighten regenerate payload mapping from diagnostics
  - improve one-click corrective loops for deficiencies
- Acceptance:
  - regeneration path resolves at least one detected deficiency class in validation tests

## Epic C — Resume Intelligence & Personalization (P1)

### C1. Resume confidence explainability
- Owner: Backend + Frontend
- Scope:
  - add “why this confidence” signals and editable overrides
  - improve role-level/scope/timeline mapping transparency
- Acceptance:
  - user sees and can edit parsed profile signals before generation

### C2. Personalization quality checks
- Owner: Backend
- Scope:
  - ensure generated projects reflect resume/self-assessment evidence (not generic output)
- Acceptance:
  - validation catches low personalization and emits actionable diagnostics

## Epic D — Conversion + Coach Workflow (P1)

### D1. Funnel instrumentation maturity
- Owner: Backend + Frontend
- Scope:
  - ensure event coverage and reliable weekly summary output
  - add conversion drop-off indicators
- Acceptance:
  - weekly summary includes stage conversion rates and top drop-off points

### D2. Coach productivity actions
- Owner: Frontend + Backend
- Scope:
  - quick feedback templates, batch review actions, regenerate recipes
- Acceptance:
  - coach can process cohort submissions faster with fewer manual edits

## Epic E — Security & Platform Hygiene (P1)

### E1. Next.js remediation execution path
- Owner: Security + Frontend
- Scope:
  - execute controlled remediation plan for Next advisories
  - capture risk/compatibility outcomes
- Acceptance:
  - documented go/no-go with validated regression set

### E2. Controls regression continuity
- Owner: Security
- Scope:
  - keep auth/session/rate-limit/webhook protections green post changes
- Acceptance:
  - security regression packs pass and checklist evidence updated

## Required Reporting Format
- Done:
  - Added backend golden snapshot regression suite with 4 deterministic scenarios anchored to charter style and structure:
    - `apps/api/tests/test_coaching_sprint13_backend.py`
    - `apps/api/tests/fixtures/sprint13_golden_sow_snapshots.json`
  - Strengthened deficiency-aware regeneration contract in diagnostics payload:
    - `regenerate_payload.contract_version`
    - `body.deficiency_context` with deficiency codes + targeted hints
    - explicit `optional` contract fields for frontend wiring.
  - Improved backend correction logic to use deficiency codes in auto-revision:
    - targeted metric-story correction
    - targeted personalization correction
    - scope mismatch correction for senior profile signals.
  - Added resume parse confidence explainability payload (`parse_confidence_explainability`) with factorized scoring + missing signal hints.
  - Added personalization validation guardrails (`PERSONALIZATION_SIGNAL_MISSING`, `PERSONALIZATION_SCOPE_MISMATCH`) to catch generic output drift.
  - Extended conversion weekly summary with `drop_off_insights` including stage sequence, per-stage drop-off rates, and top drop-off transitions.
- Validation:
  - Focused: `python -m pytest -q tests/test_coaching_sprint13_backend.py`
  - Full: `python -m pytest -q`
- Risks:
  - Golden snapshots are intentionally strict; expected-content updates require conscious fixture refresh.
  - Personalization heuristics are keyword-based and may need calibration as richer profile semantics ship.
- Needs from others:
  - Frontend to consume `regenerate_payload.body.deficiency_context` for richer one-click regenerate UX.
  - Frontend analytics views to surface `drop_off_insights.top_drop_offs` from weekly summary endpoint.

## Frontend Checkpoint Addendum (2026-03-06)
- Done:
  - Added `apps/web/scripts/install-ci.ps1` and switched `npm run install:ci` to use Windows recovery retries for `EPERM`/`ENOTEMPTY`/`EISDIR` SWC corruption signatures.
  - Expanded `apps/web/scripts/build-clean.ps1` recovery detection to include `EPERM` and `operation not permitted` failures.
  - Added coach workflow accelerators in `CoachingProjectWorkbench`:
    - quick feedback templates
    - multi-select batch review status actions
    - regenerate recipes that append corrective guidance and trigger regenerate.
  - Added resume confidence factor visibility in intake UI.
  - Added detailed checkpoint log: `docs/coaching-project/SPRINT_13_CHECKPOINT.md`.
- Validation:
  - Runtime parity confirmed under Volta pin (`node v20.11.1`, `npm 10.8.2`).
  - Deterministic run is currently blocked in this workspace by ACL-locked `node_modules/@next/swc-win32-x64-msvc/next-swc.win32-x64-msvc.node` (non-admin shell cannot clear). See checkpoint for exact commands and remediation.
- Next:
  - Add optional `parsed_jobs` carry-through from UI regeneration action to improve corrective precision.
  - Add frontend explainability card for confidence factors + missing-signal nudges.
