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
