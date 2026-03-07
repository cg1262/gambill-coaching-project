# Sprint 15 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-07
Sprint Goal: Final pilot launch readiness pass with live UX review fixes, golden quality acceptance, and operational go/no-go summary.

## Epic A — Sprint 14 Consolidation & Workspace Hygiene (P0)

### A1. Merge/push and cleanup
- Owner: Orchestrator
- Scope:
  - consolidate Sprint 14 lane commits
  - remove stray/untracked proof artifacts
  - keep local DB artifacts uncommitted
- Acceptance:
  - clean branch state with reproducible evidence references

## Epic B — Frontend Live Review Readiness (P0)

### B1. UX walkthrough fix pass
- Owner: Frontend
- Scope:
  - verify and patch issues from intake → generate → regenerate → batch review → export flow
  - preserve resume parse/edit clarity and actionable fail-reason UX
- Acceptance:
  - no blocking UX issues from live review script

### B2. Build/runtime stability recheck
- Owner: Frontend + Security
- Scope:
  - re-validate deterministic compliant-runtime proof commands
  - confirm fallback scripts/diagnostics remain robust
- Acceptance:
  - reproducible command evidence with no new regressions

## Epic C — Output Quality Acceptance (P0)

### C1. Golden scenario acceptance run
- Owner: Backend
- Scope:
  - run and verify 3–4 golden scenarios with zero major deficiencies
  - tune generation/validation if drift observed
- Acceptance:
  - golden acceptance suite green with stable artifacts

### C2. Deficiency correction loop effectiveness
- Owner: Backend + Frontend
- Scope:
  - confirm one-click regenerate resolves at least one deficiency class consistently
- Acceptance:
  - correction loop evidence captured in tests/logs

## Epic D — Conversion & Coach Throughput (P1)

### D1. Funnel + drop-off validation
- Owner: Backend
- Scope:
  - verify weekly summary and stage drop-off metrics accuracy
- Acceptance:
  - dashboard/report values match event stream expectations

### D2. Coach productivity verification
- Owner: Frontend
- Scope:
  - validate quick templates, batch actions, regenerate recipes reduce interaction overhead
- Acceptance:
  - review flow can process cohort submissions efficiently

## Epic E — Security/Ops Gate (P1)

### E1. Alert routing + checklist closeout
- Owner: Security
- Scope:
  - validate webhook invalid-signature alerts route operationally
  - refresh pilot hardening checklist and blocker status
- Acceptance:
  - clear blocker/non-blocker list and go/no-go recommendation

## End-of-Sprint Deliverable
- One-page pilot go/no-go summary:
  - Ready now
  - Remaining risks
  - Next 3 actions

## Sprint 15 Security Checkpoint (2026-03-07)
- Done:
  - Revalidated auth/session/rate-limit/webhook controls after Sprint 15 updates using focused security regression pack.
  - Revalidated invalid-signature alert routing operational path (configured webhook destination) and reconfirmed routed payload secret masking.
  - Revalidated diagnostics/personalization/runtime error output secret-safety coverage.
  - Refreshed pilot hardening checklist and POC status with updated blocker/non-blocker framing and recommendation.
- Validation:
  - `python -m pytest tests/test_auth_contract_security.py tests/test_auth_sessions.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py tests/test_llm_output_security.py` (apps/api) → **43 passed, 1 warning**
  - `python -m pytest -q tests/test_security_rate_limit_webhook.py::test_invalid_signature_alert_routes_to_configured_webhook` (apps/api) → **pass**
  - `python -m py_compile main.py webhook_security.py webhook_alerts.py coaching\sow_validation.py coaching\sow_security.py` (apps/api) → **pass**
  - `node --test scripts/require-runtime.test.cjs` (apps/web) → **5 passed**
- Risks:
  - Deterministic compliant-runtime web `typecheck/build` proof remains blocked by local Windows install/filesystem instability signatures.
- Needs from others:
  - Frontend/runtime owner to provide stable compliant-runtime runner evidence (`Node 20.11.1`, `npm 10.x`) for two consecutive successful typecheck+build runs.
- Next:
  - Keep pilot gate at **CONDITIONAL GO** (security non-blockers green; web determinism blocker open).
  - Attach this checkpoint evidence/commit SHA in pilot launch summary.

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
