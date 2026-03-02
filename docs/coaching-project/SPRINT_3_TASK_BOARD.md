# Sprint 3 Task Board — Gambill Coaching Project Creation

Last Updated: 2026-03-02
Sprint Goal: Pilot launch readiness + conversion optimization.

## Epic A — Pilot Launch Readiness (P0)

### A1. Squarespace member launch integration
- Owner: Backend + Frontend
- Scope:
  - finalize member launch flow from Squarespace page to coaching app
  - implement launch token/session bootstrap (or documented fallback flow)
- Acceptance:
  - member can launch app in <=2 clicks
  - unauthorized users blocked

### A2. Subscription lifecycle reliability
- Owner: Backend + Security
- Scope:
  - webhook signature verification + idempotency
  - renewal/cancel/grace-period behavior coverage
- Acceptance:
  - duplicate webhooks safe
  - status transitions deterministic and tested

### A3. Production readiness checks
- Owner: Security + Orchestrator
- Scope:
  - finalize pilot hardening checklist and go/no-go criteria
- Acceptance:
  - checklist complete with evidence links

## Epic B — Coach Operations (P1)

### B1. Coach workflow completion
- Owner: Frontend + Backend
- Scope:
  - notes/status filter views
  - timeline actions
  - approve/send workflow
- Acceptance:
  - coach can process submissions end-to-end without manual DB work

### B2. Batch review tooling
- Owner: Frontend
- Scope:
  - bulk status updates
  - quick next-action queue
- Acceptance:
  - coach can process 10+ submissions efficiently

## Epic C — Output Quality & Learning Outcomes (P1)

### C1. Quality score rubric v2
- Owner: Backend + Orchestrator
- Scope:
  - richer scoring dimensions (business fit, feasibility, stack relevance, clarity)
- Acceptance:
  - score card appears in output and exports

### C2. Interview-ready artifacts
- Owner: Frontend + Backend
- Scope:
  - STAR bullets
  - portfolio checklist
  - recruiter relevance mapping to job links
- Acceptance:
  - export includes interview prep package

## Epic D — Growth & Monetization (P1/P2)

### D1. Conversion instrumentation
- Owner: Backend + Frontend
- Scope:
  - track launch, generate, export, CTA clicks, upgrade intents
- Acceptance:
  - dashboard/report of funnel metrics available weekly

### D2. Mentoring recommendation optimization
- Owner: Orchestrator + Frontend
- Scope:
  - improve rationale quality and pricing presentation tests
- Acceptance:
  - measurable CTA click-through improvement in pilot

## Required Reporting Format
- Done:
- Validation:
- Risks:
- Needs from others:
- Next:
