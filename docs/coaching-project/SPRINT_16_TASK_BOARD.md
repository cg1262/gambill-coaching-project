# Sprint 16 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-07 (security + backend checkpoint)
Sprint Goal: Pilot go/no-go closeout, production-quality output gating, and coach/conversion operational readiness.
Latest security evidence: `docs/coaching-project/evidence/sprint16-security-checkpoint.log`
Latest backend evidence: `docs/coaching-project/evidence/sprint16-backend-checkpoint.log`

## Epic A — Pilot Go/No-Go Closeout (P0)

### A1. Deterministic build evidence finalization
- Owner: Frontend + Security
- Status: **In progress (security dependency unchanged)**
- Scope:
  - capture compliant-runtime deterministic build evidence from clean shell
  - ensure startup/runtime path is reproducible and documented
- Acceptance:
  - two consecutive successful cycles with evidence logs

### A2. Go/No-Go summary
- Owner: Security + Orchestrator
- Status: **Done (security one-page summary delivered)**
- Scope:
  - single-page readiness summary: ready now, blockers, mitigation timeline
- Acceptance:
  - explicit go/no-go verdict with dated next actions

## Epic B — Output Quality Production Bar (P0)

### B1. Golden quality gate hardening
- Owner: Backend
- Status: **Done (required backend gate expanded)**
- Scope:
  - enforce golden scenarios as required gate
  - zero major deficiencies for seeded scenarios
- Acceptance:
  - golden suite green and required in validation workflow

### B2. Quality trend visibility
- Owner: Backend
- Status: **Done (deterministic trend artifact committed + tested)**
- Scope:
  - add quality trend summary for seeded runs (pass/fail + top deficiency classes)
- Acceptance:
  - generated trend artifact/report available for sprint review

## Epic C — Coach Operations Throughput (P0/P1)

### C1. Batch workflow reliability
- Owner: Frontend + Backend
- Status: **Done (backend reliability + dedupe/audit assertions added)**
- Scope:
  - verify batch status/regenerate/template flows at cohort scale
- Acceptance:
  - 10+ submission flow with no blocking errors

### C2. Review auditability
- Owner: Backend
- Status: **Done (coach-action audit metadata returned by key review/batch endpoints)**
- Scope:
  - provide coach action audit trail metadata for key review actions
- Acceptance:
  - action history available for review/debug workflows

## Epic D — Conversion Funnel Optimization (P1)

### D1. Event quality + weekly summary
- Owner: Backend + Frontend
- Status: **Done (unique submission-stage counts + raw event counts validated)**
- Scope:
  - verify event completeness and stage transitions
  - expose weekly conversion/drop-off summary clearly
- Acceptance:
  - weekly summary reflects expected stage counts and top drop-offs

### D2. CTA effectiveness instrumentation
- Owner: Frontend
- Scope:
  - validate Discord/coaching CTA event capture and reporting hooks
- Acceptance:
  - CTA interactions are visible in event streams/reporting output

## Epic E — Security & Platform Hygiene (P1)

### E1. Next remediation execution checkpoint
- Owner: Security + Frontend
- Status: **Done (bounded-risk posture reaffirmed, timeline unchanged)**
- Scope:
  - execute planned remediation step or document bounded interim risk with sign-off date
- Acceptance:
  - updated posture and evidence linked in checklist docs

### E2. Control continuity
- Owner: Security
- Status: **Done (revalidated)**
- Scope:
  - maintain auth/session/rate-limit/webhook control regressions green
- Acceptance:
  - focused security pack pass and checklist updated

## End-of-Sprint Deliverable
- One-page pilot go/no-go summary:
  - `docs/coaching-project/PILOT_GO_NO_GO_SUMMARY_SPRINT16.md`

## Required Reporting Format
- Done:
  - Backend: enforced Sprint 16 production bar with required seeded/golden gate test (`apps/api/tests/test_coaching_sprint16_backend.py`) and CI workflow update (`.github/workflows/ci.yml`).
  - Backend: added deterministic seeded quality trend artifact/report (`apps/api/tests/fixtures/sprint16_seeded_quality_trend_report.json`) via `build_seeded_quality_trend_report`.
  - Backend: strengthened batch/review workflow auditability by adding `audit` metadata to review status, approve-send, review feedback, batch status, and batch regenerate responses.
  - Backend: corrected weekly conversion summary stage math to use unique submission-stage counts while preserving `raw_event_counts` for event-volume diagnostics.
  - Revalidated auth/session/rate-limit/webhook controls after Sprint 16 changes.
  - Revalidated invalid-signature alert routing path and confirmed routed payload remains secret-safe.
  - Re-ran runtime diagnostic security tests and refreshed pilot checklist + POC status with Sprint 16 evidence.
  - Documented explicit bounded-risk/no-release posture for unresolved Next.js remediation dependency.
- Validation:
  - `python -m pytest -q apps/api/tests/test_coaching_sprint14_quality_gates.py apps/api/tests/test_coaching_sprint14_seeded_artifacts.py apps/api/tests/test_coaching_sprint14_throughput_and_alerts.py apps/api/tests/test_coaching_sprint11_backend.py apps/api/tests/test_coaching_sprint13_backend.py apps/api/tests/test_coaching_sprint16_backend.py` (repo root) → **17 passed, 1 warning**.
  - `python -m pytest` (apps/api) → **167 passed, 4 skipped, 1 warning**.
  - `python -m pytest tests/test_auth_contract_security.py tests/test_auth_sessions.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py tests/test_llm_output_security.py` (apps/api) → **43 passed, 1 warning**.
  - `python -m pytest -q tests/test_security_rate_limit_webhook.py::test_invalid_signature_alert_routes_to_configured_webhook` (apps/api) → **pass**.
  - `python -m py_compile main.py webhook_security.py webhook_alerts.py coaching\sow_validation.py coaching\sow_security.py` (apps/api) → **pass**.
  - `node --test scripts/require-runtime.test.cjs` (apps/web) → **5 passed**.
  - `npm audit --omit=dev --json` (apps/web) → **1 high vulnerability (`next`)**.
- Risks:
  - Deterministic compliant-runtime web build proof remains blocker; current host still exhibits install/build instability signatures and unresolved `next` advisory requires major migration path.
- Needs from others:
  - Frontend owner: complete clean-runner deterministic `npm ci -> typecheck -> build` x2 under Node `20.11.1` / npm `10.x`.
  - Product/Ops sponsor: maintain explicit time-bounded risk acceptance until remediation timeline date gates are met.
- Next:
  - Execute Phase A clean-runner proof by 2026-03-13; complete remediation decision (secure patch/major upgrade or approved extension) by 2026-03-20.
