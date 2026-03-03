# Sprint 5 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-03
Sprint Goal: Pilot hardening closeout + deterministic web build + coach workflow completion.

## Checkpoint Update (2026-03-03 - Sprint 5 Backend Reliability + Output Quality)

### Done
- Closed P0 output-quality fit-for-sale backend refinements in `apps/api/coaching.py`:
  - expanded regeneration hint depth with structure + milestone-specificity driven guidance.
  - added stronger targeted regeneration messages for low-depth outputs even when schema passes.
- Hardened coach queue action reliability in `apps/api/main.py`:
  - added `_persist_review_state_with_retry(...)` for bounded retries + persistence consistency verification.
  - wired retry/consistency flow into:
    - `POST /coaching/review/status`
    - `POST /coaching/review/approve-send`
  - `approve-send` now requires latest generation run to be `completed` before status transition.
  - action responses now include `consistency.persist_attempts` + `consistency.persist_ok`.
- Added regression coverage:
  - retry recovery for transient review-status persistence failures.
  - approve-send guard for non-completed generation runs.
  - updated review endpoint tests for new consistency contract.
- CI/API determinism parity alignment:
  - confirmed canonical API commands are `python -m pytest -q <targets>` for focused runs and `python -m pytest -q` for full suite from `apps/api`.

### Validation
- Focused: `python -m pytest -q tests/test_coaching_review_endpoints.py tests/test_coaching_sprint2_backend.py tests/test_coaching_llm_contract.py`
- Full: `python -m pytest -q`

### Risks
- Queue retry helper is bounded and synchronous; under sustained DB instability, endpoints still fail fast after max attempts (intended).

### Needs from others
- Frontend can optionally surface `consistency.persist_attempts` in coach ops telemetry/debug view.

### Next
1. Add shared enum constants for review statuses across backend/frontend to prevent drift.
2. Add lightweight queue action metrics (retry_count, write latency, consistency failure rate).

## Epic A — Deterministic Build Closure (P0)

### A1. Web environment determinism (final)
- Owner: Frontend + Security
- Scope:
  - resolve recurring host instability (`EISDIR`, missing `tsc`/`next`) with verified deterministic install/build flow
  - pin and document Node/npm versions (`engines`, optional `.nvmrc`), lockfile strategy
  - provide one-command recovery script and troubleshooting matrix
- Acceptance:
  - from clean clone: `npm ci`, `npm run typecheck`, `npm run build` pass twice consecutively

### A2. CI alignment for web + api
- Owner: Backend + Frontend
- Scope:
  - align deterministic commands for local and CI parity
  - add concise “known failure signatures” and auto-recovery pointers
- Acceptance:
  - reproducible pass/fail signaling and clear remediation docs

## Epic B — Coach Workflow End-to-End (P0)

### B1. Queue operations reliability
- Owner: Backend + Frontend
- Scope:
  - validate notes/status filter persistence and approve/send lifecycle against real UI flow
  - harden error states and retries
- Acceptance:
  - 10-submission smoke pass with no stale state or action mismatch

### B2. Coach productivity improvements
- Owner: Frontend
- Scope:
  - quick actions and tighter queue ergonomics for triage
- Acceptance:
  - measurable reduction in clicks per reviewed submission

## Epic C — Output Quality Fit-for-Sale (P0)

### C1. Exemplar-fit project output
- Owner: Backend
- Scope:
  - deepen section quality and enforce practical artifact detail, not generic phrasing
  - strengthen weak-section hints and regeneration prompts
- Acceptance:
  - generated output is consistently coach-usable with minimal manual rewrite

### C2. Reviewer-facing diagnostics
- Owner: Frontend
- Scope:
  - render structure/quality diagnostics with clear “what to fix next” guidance
- Acceptance:
  - coach can identify and correct weak outputs in <2 minutes

## Epic D — Pilot Gate Evidence Pack (P1)

### D1. Consolidated go/no-go dossier
- Owner: Security + Orchestrator
- Scope:
  - collect test evidence, known risks, mitigations, and conditional-go criteria
- Acceptance:
  - single pilot gate doc with explicit blocker status

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
