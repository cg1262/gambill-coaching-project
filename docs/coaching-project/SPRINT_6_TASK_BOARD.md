# Sprint 6 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-03
Sprint Goal: Pilot launch + conversion instrumentation + post-launch learning loop.

## Checkpoint Update (2026-03-03 - Sprint 6 Backend Execution)

### Done
- Added pilot launch readiness backend endpoint:
  - `GET /coaching/pilot/launch-readiness`
  - validates subscription-active state, subscription-event stream presence, launch verification event, and intake completion signal.
- Implemented conversion instrumentation event capture for core backend touchpoints:
  - launch verification, intake completion, generate/regenerate, export, CTA click/mentoring intent, coach feedback capture.
  - new endpoints:
    - `POST /coaching/mentoring/intent`
    - `GET /coaching/conversion/funnel`
- Added interview-ready output package consistency layer:
  - `interview_ready_package` added to SOW contract/model with STAR bullets, portfolio checklist, recruiter mapping.
  - validation checks enforce completeness; markdown export includes interview package sections.
- Added coach feedback loop capture path and hint reuse:
  - new endpoint `POST /coaching/review/feedback`.
  - regeneration hints from recent coach feedback are merged into targeted regeneration hints during SOW generation.
- Added observability basics for generation runs:
  - generation `latency_ms` + `latency_band` and token-based `cost_band` surfaced in response/persisted validation metadata.
- Added DB schema/persistence for Sprint 6 telemetry:
  - `coaching_conversion_events`
  - `coaching_feedback_events`

### Validation
- Added focused tests:
  - `apps/api/tests/test_coaching_sprint6_backend.py`

### Risks
- Conversion/feedback event persistence is append-only and intentionally lightweight; no retention/aggregation jobs yet.
- Cost band is token-based heuristic, not billing-invoice exact spend.

### Needs from others
- Frontend wiring to call `POST /coaching/mentoring/intent` on CTA interactions.
- Product decision for final funnel reporting cadence/output destination.

### Next
- Add rolling weekly conversion summary endpoint/export artifact.
- Add tag taxonomy constraints for coach feedback tags and analytics-ready dimensions.

## Checkpoint Update (2026-03-03 - Sprint 6 Frontend Execution)

### Done
- Hardened pilot launch/member access UX in `CoachingProjectWorkbench`:
  - clearer subscription-required upgrade messaging and CTA path.
  - launch-step instrumentation and launch/access state view tracking.
  - stale issue response panel with explicit retry + fallback guidance.
- Implemented frontend conversion instrumentation wiring (`apps/web/src/lib/conversion.ts`) and event emits for:
  - launch flow view + step advance
  - upgrade CTA viewed/clicked
  - intake submit
  - generate/regenerate clicked + generation complete
  - export clicked/completed
  - mentoring CTA click
- Finalized interview-ready artifact UX and export parity:
  - added **Interview Artifacts** tab in output viewer.
  - surfaced STAR stories, portfolio checklist, recruiter requirement mapping.
  - included interview artifacts in Markdown export output.
- Implemented coach feedback tagging UI for review workflow:
  - added structured tag chips (`scope_clarity`, `business_alignment`, `architecture_depth`, `storytelling`, `portfolio_gap`, `execution_risk`).
  - tags are serialized into `coach_notes` (`[tags: ...]`) for backend quality-loop ingestion compatibility.
- Improved live issue response UX states:
  - centralized issue response panel with retry actions (queue/readiness/generation) and fallback instructions.

### Validation
- `npm run typecheck` (apps/web) ❌
  - fails in pre-existing `reactflow` type import surface (`TS2614` across `ModelCanvas.tsx`, `ErdEdge.tsx`, `TableNode.tsx`, and dependent libs).
- `npm run build` (apps/web) ❌
  - fails with `Cannot find module 'styled-jsx/package.json'` from Next require-hook (node_modules integrity issue).
- `npm run build:clean` (apps/web) ❌
  - rerun confirms same `styled-jsx` missing module failure after clean script.

### Risks
- Conversion instrumentation is currently client-local (localStorage + console) and not yet posted to backend analytics endpoint.
- Coach tags are transported via tagged note serialization until backend adds first-class tag fields.

### Needs from others
- Backend analytics endpoint contract for durable conversion event ingestion.
- Optional backend schema expansion for explicit `coach_feedback_tags` field.

### Next
1. Add backend ingestion endpoint for conversion telemetry snapshots.
2. Promote coach feedback tags to typed backend field when API contract is available.
3. Add frontend tests for interview artifacts rendering + export integrity.

## Epic A — Pilot Launch Execution (P0)

### A1. Launch runbook execution
- Owner: Orchestrator + Security
- Scope:
  - execute pilot release checklist and verify all P0 gates
  - confirm member launch flow and subscription lifecycle behavior in production-like conditions
- Acceptance:
  - pilot launch completed with no unresolved P0 blocker

### A2. Live issue response playbook
- Owner: Backend + Frontend + Security
- Scope:
  - define and test incident triage paths for auth/session/build/runtime issues
- Acceptance:
  - issue classes have owner + rollback/mitigation documented

## Epic B — Conversion & Growth Instrumentation (P0/P1)

### B1. Funnel metrics implementation
- Owner: Backend + Frontend
- Scope:
  - instrument launch, intake completion, generate/regenerate, export, CTA click, mentoring intent
  - produce weekly metrics snapshot
- Acceptance:
  - first weekly funnel report generated automatically

### B2. CTA optimization experiments
- Owner: Frontend + Orchestrator
- Scope:
  - test rationale/placement variants for mentoring recommendations
- Acceptance:
  - documented lift/no-lift with decision on winning variant

## Epic C — Learning Outcomes Package (P1)

### C1. Interview-ready outputs
- Owner: Backend + Frontend
- Scope:
  - strengthen STAR bullets, portfolio checklist, recruiter mapping consistency
- Acceptance:
  - export package consistently includes interview-ready assets

### C2. Coach feedback loop
- Owner: Backend
- Scope:
  - capture coach quality feedback tags and feed into regeneration hints/rubric updates
- Acceptance:
  - quality rubric adapts based on reviewer signal

## Epic D — Operational Maturity (P1/P2)

### D1. Cost and performance observability
- Owner: Backend + Security
- Scope:
  - track generation latency/cost bands and alert on regressions
- Acceptance:
  - baseline dashboard + alert thresholds defined

### D2. Release cadence docs
- Owner: Orchestrator
- Scope:
  - codify weekly release and retrospective cadence
- Acceptance:
  - repeatable operating loop documented and adopted

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
