# Sprint 2 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-02
Sprint Goal: Stabilize premium LLM output flow and prepare paid pilot operations.

## Epic A — Integration & Stability (P0)

### A1. Merge/normalize pass-5 commits
- Owner: Orchestrator + Backend
- Scope:
  - integrate latest frontend/backend/security outputs
  - resolve conflicts and ensure one coherent API contract
- Acceptance:
  - API tests pass
  - web typecheck/build passes
  - no broken routes in intake/generate/review/export

### A2. End-to-end regression pack
- Owner: Backend + Frontend + Security
- Scope:
  - scripted smoke checks: intake -> generate -> validate -> export
- Acceptance:
  - all smoke steps succeed in local environment
  - failures produce actionable errors

## Epic B — LLM Reliability & Quality Controls (P0)

### B1. Provider retry/timeout policy
- Owner: Backend
- Scope:
  - timeout, retry/backoff for generation calls
  - classify failures (network/provider/schema)
- Acceptance:
  - retries on transient failures
  - no silent failures

### B2. Quality threshold + regenerate action
- Owner: Backend + Frontend
- Scope:
  - compute output quality score (required sections completeness)
  - add "Regenerate with improvements" action
- Acceptance:
  - low-quality output flagged
  - regenerate path works and logs quality delta

### B3. Fallback transparency
- Owner: Frontend
- Scope:
  - visibly show when response is LLM-generated vs scaffold fallback
- Acceptance:
  - user can always tell source mode

## Epic C — Subscription & Monetization Flow (P0/P1)

### C1. Uniform premium action gating
- Owner: Backend + Frontend + Security
- Scope:
  - enforce gates for generate/export/review details
  - consistent upgrade-required UX
- Acceptance:
  - unauthorized premium attempts blocked + clear UI message

### C2. Mentoring recommendation quality
- Owner: Orchestrator + Frontend
- Scope:
  - sharpen recommendation logic display and CTA confidence copy
- Acceptance:
  - recommendation appears with rationale and clear next action

## Epic D — Coach Ops Enhancements (P1)

### D1. Coach notes and status workflow
- Owner: Backend + Frontend
- Scope:
  - add review status and coach notes fields
  - list/filter by status
- Acceptance:
  - coach can mark progress and leave notes

### D2. Submission timeline view
- Owner: Frontend
- Scope:
  - show intake, generation runs, exports, review updates in sequence
- Acceptance:
  - timeline visible per submission

## Epic E — Security & Launch Hardening (P1)

### E1. LLM startup readiness health signal
- Owner: Security + Backend
- Scope:
  - health endpoint/check for key presence and provider reachability
- Acceptance:
  - clear readiness status for pilot operations

### E2. URL and content safety hardening
- Owner: Security
- Scope:
  - strengthen generated link validation and rendering safety checks
- Acceptance:
  - unsafe links blocked/flagged with tests

## Sprint Deliverables
- Stable pilot-ready intake/generation/review/export flow
- Clear premium gating and upgrade UX
- Reliable high-quality generated SOW with transparent source mode

## Required Reporting Format (all lanes)
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
