# Sprint 11 Task Board (Backend) — Checkpoint

Date: 2026-03-05
Owner: Backend execution subagent

## Sprint Goals
- **P0 Output quality polish:** tighten charter fidelity to anchor flow, enforce milestone detail + acceptance checks, expose actionable fail reasons.
- **P0 Resume-to-project intelligence:** strengthen resume parsing confidence/signals, persist editable profile fields, map parsed signals into role/scope difficulty guidance.
- **P1 Funnel instrumentation:** ensure intake/generate/regenerate/export/CTA events are reportable in weekly conversion rollups.
- **P1 Reliability cleanup:** improve backend startup/runtime resilience for noisy local environments and upcoming app upgrade path.

## Checkpoint Status

### ✅ Completed
1. **Quality diagnostics + validation hardening**
   - Added actionable fail reason payloads (`actionable_fail_reasons`) with field pointers and suggested fixes.
   - Added stricter acceptance-check validation for milestones (`MILESTONE_ACCEPTANCE_CHECKS_NOT_ACTIONABLE`) to reduce vague outputs.
   - Kept structure + section-order enforcement intact and regeneration hints updated.

2. **Resume intelligence upgrades**
   - Resume parser now emits:
     - `parse_confidence`
     - `role_evidence`
     - stronger strength signals (including cloud visibility)
   - Intake schema now allows editable profile payloads in `preferences`:
     - `resume_profile`, `combined_profile`, `profile_overrides`
     - `stack_preferences`, `tool_preferences`
     - `resume_parse_summary`

3. **Role/scope mapping into generated SOWs**
   - Added scope-profile derivation from resume/job signals (`current_role_level`, `target_role_level`, `scope_difficulty`, timeline suggestion).
   - Injected role/scope assessment into candidate profile.
   - Mentoring CTA recommendation now ties to inferred difficulty tier.

4. **Conversion instrumentation for weekly reporting**
   - Added backend query support for windowed event retrieval.
   - Added `GET /coaching/conversion/weekly-summary` endpoint with:
     - configurable lookback window
     - event counts for intake/generate/regenerate/export/CTA/intent
     - conversion rates + daily breakdown

5. **Reliability cleanup**
   - Hardened auto-revision path against malformed payload types (e.g., string `project_story`) to prevent runtime crashes.
   - Added resilient fallback in feedback-event reads when local DuckDB lock/IO exceptions occur.
   - Secret masking now also applies to interview-ready narrative composition inputs.

6. **Test coverage + verification**
   - Added `test_coaching_sprint11_backend.py` for Sprint 11 features.
   - Focused tests passed.
   - Full backend pytest run passed.

## POC Status
- **POC A (Quality diagnostics UX contract):** ✅ validated in backend response payload.
- **POC B (Resume signal confidence + editable profile persistence):** ✅ validated via parser + intake model tests.
- **POC C (Weekly conversion reporting API):** ✅ endpoint implemented and covered by API test.
- **POC D (Resilience under malformed SOW + DB lock pressure):** ✅ backend now degrades safely instead of hard-failing.

## Notes / Follow-ups
- Consider adding SQL-level weekly aggregation views if event volume grows beyond API-side rollups.
- Consider surfacing `scope_difficulty` and parse confidence explicitly in UI coaching controls for coach overrides.
