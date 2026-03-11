# Handoff - Meta-Rubric Gate (2026-03-11)

## Objective
Enforce project-generation quality so output must meet the meta-rubric confidence threshold (>=85 by default), otherwise automatically reprocess with a different project direction.

## Completed
- Added a generator wrapper that enforces the meta-rubric threshold and retries with alternate archetypes when the initial score is below threshold.
- Added gate metadata to generation meta:
  - `meta_rubric_gate`
  - `meta_rubric_evaluation`
- Rewired package export so `coaching.generate_sow_with_llm` uses the gated wrapper.
- Restored and validated DOCX export behavior in API response payload:
  - `format=docx`
  - `mime_type=application/vnd.openxmlformats-officedocument.wordprocessingml.document`
  - `content_base64`
- Recovered a transient file truncation incident (`CoachingProjectWorkbench.tsx`) by restoring from `HEAD`.

## Files Changed For This Increment
- `apps/api/coaching/sow_generation_gate.py` (new)
- `apps/api/coaching/__init__.py`
- `apps/api/main.py`
- `apps/api/tests/test_coaching_meta_rubric_gate.py` (new)

## Test Evidence
Command:
`py -3.11 -m pytest apps/api/tests/test_coaching_meta_rubric_gate.py apps/api/tests/test_coaching_llm_contract.py apps/api/tests/test_coaching_sprint6_backend.py -q`

Result:
- `15 passed`
- 1 existing pydantic warning (non-blocking)

## Config Notes
- Threshold env var:
  - `COACHING_META_RUBRIC_MIN_SCORE` (default `85`)
  - bounded to `50..99` by implementation

## Known Risks / Follow-Ups
- `main.py` still contains large legacy sections and is currently brittle with patch-timeout behavior in this environment; future changes should use very small edit chunks.
- Add UI surface for `meta_rubric_gate` in workbench so coaches can see why a reprocess happened.
- Add an API endpoint test to confirm gate metadata is persisted in generation run history.

## Suggested Next Sprint
1. Surface `meta_rubric_gate` details in review UI (status, threshold, initial/final score, selected archetype).
2. Add backend tests for persistence of gate metadata in `save_coaching_generation_run`.
3. Add configurable policy for reprocess attempt count and archetype ordering.
4. Add support-playbook content for handling frequent upstream provider failures (timeouts/rate limits/auth) with clearer user-facing diagnostics.
