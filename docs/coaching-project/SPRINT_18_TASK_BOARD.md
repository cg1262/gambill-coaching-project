# Sprint 18 Task Board - Gambill Coaching Project Creation

Last Updated: 2026-03-10 (completed)
Sprint Goal: Ship measurable quality gains in generated projects via evaluation harnessing, explicit planner/reviewer generation passes, and durable run-history re-export workflows.

## Sprint Start Plan (Locked)
1. Build an evaluation harness with category scoring and optional gold-standard reference alignment.
2. Add a two-pass planner -> reviewer generation flow and expose pass diagnostics.
3. Make exports run-history-aware (`run_id` and latest persisted run fallback), including Word support.

## Epic Status

### Epic A - Evaluation Harness (P0)
- A1. Rubric scoring contract: **Completed**
- A2. Gold-standard reference alignment: **Completed**

### Epic B - Two-Pass Generation (P0)
- B1. Planner -> reviewer/fixer pipeline: **Completed**
- B2. Pass telemetry: **Completed**

### Epic C - Run-History Re-Export (P0)
- C1. Export from persisted runs: **Completed**
- C2. Frontend wiring for run-based export: **Completed**

## Sprint End Report

### Done
- Added evaluation module: `apps/api/coaching/sow_evaluation.py` with rubric scoring for scope clarity, architecture depth, KPI specificity, and interview readiness.
- Added optional reference alignment scoring (`md/txt/docx`) and reference-document load diagnostics.
- Added API endpoint `POST /coaching/sow/evaluate` with three SOW source modes: request payload, `run_id`, and latest run via `submission_id`.
- Added DB helper `get_coaching_generation_run(run_id)` and wired run-based export resolution.
- Extended export endpoint to support `run_id`/latest run fallback when `sow` is omitted and preserved markdown/json/docx outputs.
- Added JSON export metadata for run-based exports (`run_id`, `filename`, `mime_type`) for parity with docx path.
- Implemented two-pass reviewer behavior in `apps/api/coaching/sow_draft.py` with apply-only-if-improved logic.
- Hardened generation metadata shaping in `main.py` so review-pass diagnostics are safely returned in responses and persisted validation.
- Updated frontend export wiring in workbench/api client for persisted run re-export after reopening submissions.
- Added Sprint 18 backend tests in `apps/api/tests/test_coaching_sprint18_backend.py` for evaluate/export/reviewer behaviors.

### Validation
- Backend:
  - `py -3.11 -m pytest apps/api/tests/test_coaching_sprint18_backend.py apps/api/tests/test_coaching_sprint6_backend.py -q`
  - Result: `10 passed`
- Frontend:
  - `npm run typecheck` (from `apps/web`)
  - Runtime check passed with Node `20.11.1` and npm `10.8.2`.

### Risks
- Fallback frequency can still spike with weak or ambiguous intake inputs; additional prompt/rubric tuning is still needed.
- Reference alignment is lexical token-overlap today, not semantic similarity scoring.
- This pass ran focused tests, not the full backend regression suite.

### Learnings
- Run-history-aware export is essential for real coach workflow continuity.
- Safe metadata shaping keeps response payloads useful without leaking noisy internal details.
- Smaller, incremental edits are more reliable in this workspace than large monolithic patches.
- Meta-rubrics should be separated clearly: SOW generation quality vs student implementation quality.

### Needs From Others
- 8-15 approved gold-standard projects to calibrate rubric weighting and pass/fail thresholds.
- Decision on launch gating threshold for `meets_gold_standard_bar`.

### Next Sprint Candidates
1. Reduce fallback frequency with targeted failure clustering and prompt/rubric refinement loops.
2. Add semantic reference alignment (embedding-based) and compare against lexical alignment output.
3. Surface `/coaching/sow/evaluate` output directly in coach UI for explicit quality-gate review.
