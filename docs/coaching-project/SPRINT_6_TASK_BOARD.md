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
- Standardized web runtime contract to Node 20 LTS (pinned 20.11.1) with docs/runtime alignment:
  - `.nvmrc`, `package.json engines`, and `apps/web/README.md` now explicitly aligned to Node 20 LTS + npm 10.
- Added admin-ready rate-limit UX scaffolding in `CoachingProjectWorkbench`:
  - hidden internal panel (`?internal=1` / `?admin=1`) for editable fallback retry seconds + helper messaging.
  - local persistence via `localStorage` (`src/lib/rateLimitConfig.ts`) as bridge until API-backed admin settings exist.
- Added 429-aware API error handling (`src/lib/api.ts`):
  - structured `ApiError` with status + parsed `Retry-After` support.
  - surfaced actionable retry guidance in UI with wait-window messaging and explicit retry actions.

### Validation
- `npm run typecheck` (apps/web) ✅ pass.
- `npm run build` (apps/web) ❌
  - fails with persistent filesystem issue: `EISDIR ... node_modules/next/dist/pages/_app.js`.
- `npm run build:clean` (apps/web) ❌
  - clean flow runs module recovery (`npm ci`) and retries once, but still fails with `EISDIR ... src/app/project/[id]/page.tsx`.

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

## Checkpoint Update (2026-03-03 - Sprint 6 Security Execution)

### Done
- Re-validated generic auth/session denial contracts and no-leak behavior on protected coaching routes.
- Expanded security regression coverage:
  - `apps/api/tests/test_auth_contract_security.py`
    - added generic 401 contract checks for:
      - `GET /coaching/subscription/status`
      - `GET /coaching/subscription/lifecycle-readiness`
  - `apps/api/tests/test_coaching_security_access.py`
    - added generation instrumentation/log payload regression ensuring summary-only event telemetry does not expose raw resume/self-assessment/email secrets.
  - `apps/api/tests/test_llm_output_security.py`
    - expanded unsafe URL regression set with `file://` payload blocking in generated SOW surfaces.
  - `apps/api/tests/test_coaching_subscription.py`
    - added lifecycle-readiness event sanitization assertions (no raw `payload_json`/signature leakage).
    - strengthened idempotent replay assertions so replay status/`active` derive from stored event truth, not incoming replay payload.
- Hardened subscription lifecycle API behavior in `apps/api/main.py`:
  - `GET /coaching/subscription/lifecycle-readiness` now returns sanitized recent-event summaries only.
  - `POST /coaching/subscription/sync` replay branch now computes `active` from replay status derived from persisted event payload.
- Updated pilot hardening checklist + POC status with Sprint 6 evidence and blocker/non-blocker split.

### Validation
- API security pack (from `apps/api`):
  - `python -m pytest tests/test_auth_contract_security.py tests/test_llm_output_security.py tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_subscription.py`
  - Result: **52 passed, 1 warning**.
- API compile check:
  - `python -m compileall -q .` → **pass**.
- Web checks (from `apps/web`):
  - `npm run typecheck` → **pass**.
  - `npm run build:clean` → **fail** (persistent `EISDIR` on `node_modules/next/dist/pages/_app.js` after scripted `npm ci` retry).

### Risks
- **Blocker:** deterministic web clean build remains blocked by persistent filesystem/module corruption signature (`EISDIR` in Next build path), so full pilot release evidence cannot be marked complete.
- **Blocker:** provider webhook signature verification and route-level rate limiting are still not implemented.
- **Non-blocker:** auth/session denial contracts, output URL safety, diagnostics/output sanitization, and subscription replay/event-summary controls are regression-backed and passing.

### Needs from others
- Product/ops sign-off on whether pilot can proceed as **conditional go** with current production blockers still open.
- Platform/devops support to resolve persistent `EISDIR` host build failure and pin supported Node/npm runtime for deterministic web builds.

### Next
1. Implement provider webhook signature verification (Stripe/Squarespace) with invalid-signature alerting.
2. Add route-level rate limiting for `/auth/*` and subscription routes.
3. Resolve `EISDIR` build blocker and attach final clean build logs + commit SHA to pilot launch notes.

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
