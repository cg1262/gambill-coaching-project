# Sprint 12 Task Board (Backend Golden Quality + Regeneration Contract)

Date: 2026-03-05
Owner: Gambill Claw

## Scope
P0
1. Golden-output acceptance tests anchored to style exemplars (GlobalMart + VoltStream) with at least 3 scenarios.
2. Tighten structure/tone/depth guardrails so golden runs return zero major deficiencies.
3. Improve deterministic resume-signal to scope/timeline mapping quality.
4. Expose frontend-ready deficiency-aware regenerate payload contract.
5. Run focused and full backend pytest with evidence.

## Completed
- Added `apps/api/tests/test_coaching_sprint12_backend.py` with 5 tests including:
  - 3 golden acceptance scenarios (senior retail, mid energy, foundational junior)
  - deterministic scope/timeline tie-stability check
  - regenerate payload contract assertion for frontend trigger wiring
- Improved scope/timeline mapping in `apps/api/coaching/sow_draft.py`:
  - deterministic majority vote for target seniority (stable tie behavior)
  - capability index blending tools/domains/project signals
  - parse-confidence and years-aware difficulty/timeline mapping
  - preference timeline integration with bounded guardrails
- Tightened quality/rubric logic in `apps/api/coaching/sow_validation.py`:
  - new story-depth check (`PROJECT_STORY_DEPTH_WEAK`)
  - new metric-signal check (`PROJECT_STORY_METRIC_SIGNAL_MISSING`)
  - added major deficiency rollup (`major_deficiency_codes`, `major_deficiency_count`)
  - added `regenerate_payload` contract for direct frontend trigger of `/coaching/sow/generate`
- Updated generation endpoint wiring in `apps/api/main.py` to inject `workspace_id` and `submission_id` into diagnostics regenerate payload.
- Updated auto-revision defaults in `apps/api/coaching/sow_completion.py` to maintain stronger executive narrative depth and KPI-oriented tone.

## Validation
From `apps/api`:
- Focused:
  - `python -m pytest -q tests/test_coaching_sprint12_backend.py`
- Full:
  - `python -m pytest -q`

## Notes
- Regenerate payload is intentionally response-native and backend-authenticated to keep frontend orchestration simple.
- Major deficiency rollup is additive; no breaking contract removal for existing diagnostics consumers.

---

## Frontend Execution Addendum (2026-03-05)

### Completed
- Finalized quality fail-reason UX in `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`:
  - introduced actionable deficiency cards sourced from `quality_diagnostics.actionable_fail_reasons`
  - mapped deficiency codes/fields to specific output tabs (`charter`, `milestones`, `dataSources`, `resources`, `story`)
  - added one-click path buttons to jump directly to impacted section and one-click targeted regenerate (`regenerate_with_improvements=true`)
- Improved resume confidence/edit UX polish:
  - strengths/gaps are now fully editable with add/remove controls
  - added intake mapping preview panel showing what review sees from resume profile payload
- Improved review visibility for intake/review mapping:
  - added `Resume/Profile Mapping Snapshot` card in submission detail showing confidence, highlights, strengths, gaps, and combined profile narrative.
- Preserved readability upgrades for charter/milestone/source sections (no structural rollback; output viewer tab structure unchanged).
- Hardened `apps/web/scripts/build-clean.ps1` runtime detection to use `npm_node_execpath` fallback so Node version parsing does not null-fail under packaged runtime invocations.

### Validation Evidence
From `apps/web`:
- `npx -y -p node@20.11.1 -p npm@10.8.2 -c "npm ci --no-audit --no-fund"` → pass
- `npx -y -p node@20.11.1 -c "node ./scripts/require-runtime.cjs && node ./node_modules/typescript/bin/tsc --noEmit"` → pass
- `npx -y -p node@20.11.1 -c "node ./scripts/require-runtime.cjs && node ./node_modules/next/dist/bin/next build"` → fail with persistent environment signature: `EISDIR: illegal operation on a directory, readlink ... node_modules/next/dist/pages/_app.js`
- `npm run build:clean` under compliant runtime wrapper now executes parity checks and recovery path correctly, but retry still fails with same persistent `EISDIR` signature.

### Open Blocker
- Required acceptance item "two consecutive successful typecheck+build runs on Node 20.11.1/npm 10.x" remains blocked by persistent host filesystem/module corruption signature (`EISDIR readlink ... next/dist/pages/_app.js`) despite clean install and scripted recovery retries.
