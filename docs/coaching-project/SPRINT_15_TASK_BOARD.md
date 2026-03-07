# Sprint 15 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-07 (frontend live-review pass)
Sprint Goal: Final pilot launch readiness pass with live UX review fixes, golden quality acceptance, and operational go/no-go summary.
Latest frontend evidence: `docs/coaching-project/evidence/sprint15-frontend-live-review.log`

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
- Status: **Done (2026-03-07)**
- Completed:
  - patched plan-tier lock so review queue + mentoring gates can be validated in-session
  - unified timeline state across self-assessment and preferences to prevent payload drift
  - upgraded actionable fail-reason UX to append fix notes + jump tab + regenerate in one click
  - added generate guard to prevent duplicate concurrent regenerate calls
- Evidence:
  - `docs/coaching-project/evidence/sprint15-frontend-live-review.log`
- Acceptance:
  - no blocking UX issue observed in intake → generate → regenerate → batch-review → export path under scaffolded flow

### B2. Build/runtime stability recheck
- Owner: Frontend + Security
- Status: **Done (frontend revalidation complete)**
- Completed:
  - re-ran deterministic runtime unit tests (`npm run runtime:test`) ✅
  - re-ran startup runtime gate (`npm run runtime:check`) with expected fail-fast diagnostics on Node 24/npm 11 host ✅
  - re-ran TypeScript compile (`npx tsc --noEmit`) ✅
  - noted lint command currently interactive due missing ESLint baseline config (non-blocking for runtime diagnostics)
- Evidence:
  - `docs/coaching-project/evidence/sprint15-frontend-live-review.log`
- Acceptance:
  - deterministic runtime diagnostics still reproducible and explicit

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
- Status: **In progress**
- Frontend support completed:
  - fail-reason cards now support direct “apply fix + regenerate” workflow with note carryover
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
- Status: **Done (UX friction reductions validated)**
- Completed:
  - quick templates, feedback tags, regenerate recipes, and batch queue actions all accessible once tier is set to Pro/Elite
  - one-click fail-reason repair now pre-populates coach notes for faster review loops
- Evidence:
  - `docs/coaching-project/evidence/sprint15-frontend-live-review.log`

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

## Required Reporting Format
- Done:
  - Frontend live-review blockers patched (plan tier gating, timeline sync, actionable fail-reason regenerate, duplicate generate guard).
- Validation:
  - `npm run runtime:test` pass; `npm run runtime:check` expected fail-fast message on non-compliant host runtime; `npx tsc --noEmit` pass.
- Risks:
  - `npm run lint` is currently interactive (no committed ESLint baseline), so lint is not yet CI-automatable.
- Needs from others:
  - Backend golden scenario acceptance + deficiency loop evidence completion.
- Next:
  - Add non-interactive ESLint baseline config and wire lint into deterministic frontend CI gate.
