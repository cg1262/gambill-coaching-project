# Demo Readiness Tasks (Focused Wedge)

Last Updated: 2026-02-27
Goal: Reach reliable, repeatable, investor/client-ready demo state for the governance + blast-radius wedge.

## Priority 0 (Must Have Before Demo)

### P0-1 Databricks schema import reliability
- Add explicit schema diagnostics (schemas discovered, selected schema, table/column counts)
- Preserve clear success/failure messaging
- Add retry-safe import behavior for large object sets

**Done when:**
- import succeeds/fails with actionable message in all tested scenarios

### P0-2 Blast radius fidelity baseline
- Ensure imported entities are valid inputs to impact engine
- Improve source/confidence attribution in dependency cards
- Validate deterministic impact on imported schema changes
- ✅ Added coaching exercise runner that executes validation + impact + findings in sequence to harden end-to-end flow

**Done when:**
- blast radius output is non-empty and explainable for a representative schema change

### P0-3 Standards lifecycle confidence
- Validate standards findings -> status update -> audit timeline loop
- Add missing note UX where required
- Ensure bulk status actions are reliable

**Done when:**
- lifecycle changes are visible, persisted, and auditable in one pass

### P0-4 Security/reliability floor
- Stabilize auth/session behavior for demo runs
- Confirm secrets redaction on read paths
- Add smoke tests for auth + standards/report routes

**Done when:**
- no auth or secret leakage issues in demo walkthrough

---

## Priority 1 (Strongly Recommended)

### P1-1 PR artifact automation quality
- Strengthen provider posting diagnostics
- Add idempotency key for pipeline-triggered posting
- Improve error messages for token/permission failures

### P1-2 Audit UX scale
- Add status/user/date filters + pagination controls to UI
- Keep response time stable with larger logs

### P1-3 Demo controls
- Add one-click “demo readiness” check endpoint + panel
- Show connector status, latest run counts, and blockers

---

## Priority 2 (Post-Demo)
- Deeper dependency ingest (pipelines/notebooks/BI)
- Ownership/SLA fields for findings
- Expanded integration test and E2E coverage

---

## Suggested Execution Sequence (1-week sprint)
Day 1-2: P0-1 + P0-4
Day 3: P0-2
Day 4: P0-3
Day 5: P1-3 + polish + dry-run script

---

## Demo Success Criteria
- Import Databricks schema
- Run standards and update finding status
- Show audit trail
- Run blast radius for model change
- Publish PR artifacts
- Complete flow with no manual backend intervention
