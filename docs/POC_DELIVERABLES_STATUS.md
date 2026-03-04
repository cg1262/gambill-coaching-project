# POC Deliverables Status

Last Updated: 2026-03-04
Owner: ERD Program Team

## Checkpoint Update (2026-03-04 - Sprint 9 Frontend Execution: Intake UX + Charter Review Flow)

### Done
- Reworked intake resume step with drag/drop zone + file picker and explicit upload/parse status indicators.
- Added editable resume highlight extraction flow so coaches can refine parsed bullets before submit.
- Updated intake submit payload composition to combine self-assessment + resume-derived profile signals.
- Added `preferences.resume_profile` and `preferences.combined_profile` for cleaner downstream profile merge handling.
- Redesigned output viewer with a default `Project Charter` narrative section at top for reviewer-first context.
- Upgraded data source section with prominent ingestion instruction block.
- Upgraded milestone rendering into card hierarchy with expectations, deliverables, and acceptance checks.
- Improved spacing and typography affordances for reviewer scanning.

### Validation
- `powershell -ExecutionPolicy Bypass -File .\run-coaching.ps1 -RuntimeCheckOnly` (repo root) → **pass** (auto-remediated runtime to Node `20.11.1` / npm `10.8.2`).
- `C:\Program Files\Volta\volta.exe run --node 20.11.1 --npm 10.8.2 npm run typecheck` (apps/web) → **pass**.
- `C:\Program Files\Volta\volta.exe run --node 20.11.1 --npm 10.8.2 npm run build` (apps/web) → **fails** with pre-existing deterministic corruption signature (`EISDIR readlink next/dist/pages/_app.js`, then `EPERM .next/trace`).

### Risks / Follow-ups
- Resume parsing in browser uses text extraction heuristics; richer PDF/docx extraction may need dedicated parsing lib/service.
- Resolve Windows `next` build corruption (`EISDIR`/`EPERM`) via lock recovery + fresh module install before release build signoff.

## Checkpoint Update (2026-03-04 - Sprint 9 Backend Execution: Resume Intelligence + Charter Flow Quality)

### Done
- Added resume upload intake endpoint `POST /coaching/intake/resume/upload` supporting `pdf/docx/txt` via multipart file input.
- Implemented resume text extraction helpers for txt/docx/pdf and signal extraction (`role_level`, `tools`, `domains`, `project_experience_keywords`, `strengths`, `gaps`) using deterministic heuristics.
- Added fallback handling when extraction fails (`fallback_used`, `parse_warning`) so intake can still continue with pasted text.
- Persisted parsed resume summary into intake preferences (`preferences.resume_parse_summary`) and added DB update helper for in-place preference updates.
- Expanded SOW scaffold/validation with GlobalMart-style charter flow under `project_charter` enforcing ordered sections:
  - `prerequisites_resources`
  - `executive_summary`
  - `technical_architecture`
  - `implementation_plan`
  - `deliverables_acceptance_criteria`
  - `risks_assumptions`
  - `stretch_goals`
- Strengthened charter requirements for realistic narrative, public data links, ingestion docs, and milestone completion criteria expectations.
- Added sprint-9 backend tests for resume parse + fallback behavior and charter section-order validation.

### Validation
- `python -m pytest -q tests/test_coaching_sprint9_backend.py` (apps/api) → **pass**.

### Risks / Follow-ups
- PDF extraction currently uses lightweight heuristic parsing; scanned/image PDFs still require manual paste fallback or OCR in future sprint.

## Checkpoint Update (2026-03-04 - Sprint 8 Security Execution: Runtime Policy Regression + Pilot Gate Revalidation)

### Done
- Re-reviewed permanent runtime policy implementation for operational safety in `apps/web` and confirmed contract pinning/guard flow remains intact.
- Refactored runtime enforcement script (`apps/web/scripts/require-runtime.cjs`) into testable helpers while preserving fail-fast behavior.
- Added secret-like diagnostic redaction coverage in runtime mismatch messaging to reduce leakage risk in failure paths.
- Added runtime regression tests in `apps/web/scripts/require-runtime.test.cjs` and wired script `npm run runtime:test`.
- Re-ran security regression packs and API compile checks; refreshed Sprint 8 and pilot checklist docs with latest evidence.

### Validation
- `npm run runtime:test` (apps/web) → **4 passed**.
- `npm run typecheck` (apps/web) → **expected fail-fast** on host runtime mismatch (`Node v24.13.1`, `npm 11.8.0`).
- `npm run build:clean` (apps/web) → **expected fail-fast** on host runtime mismatch.
- `python -m pytest tests/test_auth_contract_security.py tests/test_llm_output_security.py tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_subscription.py` (apps/api) → **52 passed, 1 warning**.
- `python -m pytest -q tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py` (apps/api) → **14 passed, 1 warning**.
- `python -m compileall -q .` (apps/api) → **pass**.

### Risks / Follow-ups
- Final deterministic web success sequence (`npm ci`, `typecheck`, `build`, `build`) still requires compliant runtime host/runner (`Node 20.11.1`, `npm 10.x`).
- Production alerting for repeated invalid webhook signatures remains pending.

## Checkpoint Update (2026-03-03 - Sprint 8 Frontend Execution: Runtime Policy Permanence + Review UX Confirmation)

### Done
- Made runtime policy persistent in `apps/web` package contract:
  - retained `engines` (`node >=20.11.1 <21`, `npm >=10 <11`)
  - retained `packageManager` pin (`npm@10.8.2`)
  - added `volta` pin metadata (`node: 20.11.1`, `npm: 10.8.2`)
  - kept `.nvmrc` aligned (`20.11.1`).
- Hardened deterministic install/build script surface:
  - added `npm run install:ci` -> `npm ci --no-audit --no-fund`
  - added `npm run verify:deterministic` -> install/typecheck/build/build
  - kept runtime guard fail-fast on `dev`, `typecheck`, `build`, and `build:clean`.
- Updated `apps/web/README.md` with runtime pinning hierarchy and actionable remediation flow.
- Confirmed/finalized UX review items in coaching workbench remain in place:
  - stale session banner reset via centralized auth stale-state clear and authenticated-success reset path
  - explicit self-assessment field labels for confidence controls
  - tools/platform exposure checkbox UX + `Other` conditional fields
  - clearer constraints/support labels and helper copy
  - diagnostics + regenerate guidance shown in readable, actionable list format.

### Validation
- From `apps/web` on host runtime Node `v24.13.1` + npm `11.8.0`:
  - `npm run runtime:check` -> **expected fail-fast** with remediation guidance.
  - `npm run typecheck` -> **expected fail-fast** (blocked by runtime gate).
  - `npm run build` -> **expected fail-fast** (blocked by runtime gate).
  - `npm run build:clean` -> **expected fail-fast** (blocked by runtime gate).
- Runtime gate output explicitly confirms required baseline: Node `>=20.11.1 <21`, npm `10.x`.

### Risks / Follow-ups
- Final deterministic green evidence (`typecheck`, `build`, `build:clean` passing) still requires execution under compliant runtime (Node `20.11.1` + npm `10.x`).

## Checkpoint Update (2026-03-03 - Sprint 8 Backend Execution: Runtime/Rate-Limit Config Contract Alignment)

### Done
- Added admin config API surface to bridge frontend runtime/rate-limit scaffolding to backend policy contract:
  - `GET /admin/security/runtime-rate-limit-config`
  - `PUT /admin/security/runtime-rate-limit-config`
- Implemented new backend config module `apps/api/admin_runtime_config.py` with:
  - `web_runtime` policy metadata (Node/npm requirements + preflight scripts + enforcement reference)
  - `rate_limit_ui` fallback contract (`default_retry_seconds`, `helper_message`) with frontend-friendly camelCase aliases.
- Added frontend API types/methods in `apps/web/src/lib/api.ts` for runtime/rate-limit admin config retrieval and updates.
- Added regression test `apps/api/tests/test_coaching_sprint8_backend.py` to validate contract fields and update roundtrip semantics.

### Validation
- Focused backend command (`apps/api`):
  - `python -m pytest -q tests/test_coaching_sprint8_backend.py tests/test_coaching_sprint7_backend.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py`
  - Result: **18 passed, 1 warning**.
- Full backend suite (`apps/api`):
  - `python -m pytest -q`
  - Result: **128 passed, 4 skipped, 1 warning**.

### Risks / Follow-ups
- Current runtime/rate-limit admin config is in-memory/env-default backed and not yet persisted as workspace-scoped policy state.
- Frontend internal admin panel still uses localStorage-only save path; API contract is now available but not yet wired into that UI.

## Checkpoint Update (2026-03-03 - Sprint 7 Backend Execution: Webhook/Idempotency Hardening + Subscription Ops Readiness)

### Done
- Tightened subscription event idempotency in integrated pilot paths (`/coaching/subscription/sync`, `/coaching/subscription/webhook`) by deriving deterministic event IDs when provider IDs are absent.
- Added explicit replay trace field in sync/webhook responses: `idempotency_key_source` (`provider_event_id` vs `derived`).
- Verified and enforced subscription throttling across operationally critical endpoints:
  - `POST|GET /coaching/subscription/status`
  - `GET /coaching/subscription/lifecycle-readiness`
  - `GET /coaching/pilot/launch-readiness`
  - `POST /coaching/subscription/sync`
  - `POST /coaching/subscription/webhook`
- Extended parameterized rate-limit config support for subscription traffic with `RATE_LIMIT_SUBSCRIPTION_USER_BURST`.
- Added Sprint 7 backend evidence tests in `apps/api/tests/test_coaching_sprint7_backend.py`:
  - derived-id idempotent replay,
  - admin override endpoint operational verification (`GET|PUT /admin/security/rate-limits`),
  - controlled backend pilot trace (intake→generate→regenerate→export→review feedback) with conversion + feedback integrity assertions.

### Validation
- Focused command (`apps/api`):
  - `python -m pytest -q tests/test_coaching_sprint7_backend.py tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py`
  - Result: **17 passed, 1 warning**.
- Full backend suite (`apps/api`):
  - `python -m pytest -q`
  - Result: **131 passed, 4 skipped, 1 warning**.

### Risks / Follow-ups
- Derived idempotency keying intentionally dedupes payload-equivalent no-provider-ID events; confirm desired semantics for provider edge cases.
- Invalid webhook signature alerting remains an ops control follow-up (rejection path is enforced; alert pipeline still pending).

## Checkpoint Update (2026-03-03 - Sprint 7 Frontend Execution: Runtime Parity Gate + Quality-Loop Prompt Tightening)

### Done
- Implemented runtime parity fail-fast controls for `apps/web` to address root-cause conditions behind recurring deterministic `EISDIR/readlink` signatures under runtime drift.
- Added strict runtime guard script:
  - `apps/web/scripts/require-runtime.cjs`
  - baseline: Node `>=20.11.1 <21`, npm `10.x`
  - wired into `predev`, `pretypecheck`, `prebuild`, and `prebuild:clean` in `apps/web/package.json`.
- Hardened clean-build script in `apps/web/scripts/build-clean.ps1`:
  - strict runtime parity assertion before build/recovery
  - source path integrity checks on critical app route files to catch file/dir corruption signatures early.
- Updated web runtime/build docs in `apps/web/README.md` with explicit parity behavior and actionable remediation flow.
- Tightened coaching quality-loop UX prompts in `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`:
  - diagnostics-derived suggested feedback tags
  - human-readable feedback tag labels
  - one-click “Apply suggested tags” action
  - dynamic coach prompt draft text for reviewer notes.
- Ran controlled pilot flow validations at contract level:
  - intake -> generate -> export regression
  - review approve/send handoff regression.

### Validation
- From `apps/web` (host runtime: Node `v24.13.1`, npm `11.8.0`):
  - `npm run typecheck` -> **fail-fast expected** with runtime mismatch guidance.
  - `npm run build` -> **fail-fast expected**.
  - `npm run build:clean` -> **fail-fast expected**.
- From `apps/api`:
  - `python -m pytest -q tests/test_security_sprint2.py::test_a2_security_regression_flow_intake_generate_validate_export tests/test_coaching_review_endpoints.py::test_review_approve_send_generates_launch_token`
  - Result: **2 passed, 1 warning**.

### Risks / Follow-ups
- Deterministic web clean-build **success proof** is pending execution on compliant runtime (Node `20.11.1` + npm `10.x`).
- This host currently validates fail-fast parity behavior only; final green sequence still needs a compliant runner.

## Checkpoint Update (2026-03-03 - Sprint 7 Security Execution + Pilot Gate Refresh)

### Done
- Executed Sprint 6 security validation on coaching API auth/session, generation safety, telemetry payload hygiene, and subscription lifecycle controls.
- Preserved generic denial contracts and expanded coverage:
  - `apps/api/tests/test_auth_contract_security.py` now includes protected 401 contract checks for:
    - `GET /coaching/subscription/status`
    - `GET /coaching/subscription/lifecycle-readiness`
- Expanded instrumentation/event payload safety regression:
  - `apps/api/tests/test_coaching_security_access.py` now verifies `coaching_sow_generate_completed` logging remains summary-only and does not leak raw resume/self-assessment/email secrets.
- Expanded output safety regressions:
  - `apps/api/tests/test_llm_output_security.py` now includes `file://` URL blocking in generated SOW sanitization checks.
- Hardened subscription lifecycle endpoint behavior in `apps/api/main.py`:
  - `GET /coaching/subscription/lifecycle-readiness` now returns sanitized event summaries (no raw `payload_json` echo).
  - `POST /coaching/subscription/sync` idempotent replay now derives `active` from persisted replay event status.
- Expanded subscription lifecycle regression set:
  - `apps/api/tests/test_coaching_subscription.py` now verifies lifecycle-readiness redacts raw event payload fields and replay status consistency.
- Updated Sprint 6 task board and pilot hardening checklist with blocker/non-blocker security checkpoint status and refreshed evidence commands.
- Added webhook verification security controls + tests:
  - `POST /coaching/subscription/sync` enforces provider/shared-secret signature + timestamp checks when webhook secret is configured.
  - `POST /coaching/subscription/webhook` timestamp/signature rejection paths are regression-covered.
  - Regression suite `apps/api/tests/test_security_rate_limit_webhook.py` now covers valid/invalid/missing signature paths, replay-safe duplicate event handling, timestamp window rejection, and no-leak rejection behavior.
- Closed route-level throttling gap for subscription surfaces:
  - Added `subscription` rate-limit policy in `apps/api/rate_limits.py`.
  - Enforced throttling on `GET /coaching/subscription/status`, `POST /coaching/subscription/status`, `POST /coaching/subscription/sync`, and `POST /coaching/subscription/webhook`.
  - Added regression coverage for generic 429 denial payloads on status/sync routes.
- Validated override model auditability for throttling changes via `GET|PUT /admin/security/rate-limits` snapshot/update controls.

### Validation
- Security pack run (from `apps/api`):
  - `python -m pytest tests/test_auth_contract_security.py tests/test_llm_output_security.py tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py tests/test_coaching_subscription.py`
  - Result: **52 passed, 1 warning**.
- API compile check:
  - `python -m compileall -q .` → **pass**.
- Focused security regression add-on (from `apps/api`):
  - `python -m pytest -q tests/test_security_rate_limit_webhook.py tests/test_rate_limits_and_webhooks.py tests/test_coaching_subscription.py`
  - Result: **13 passed, 1 warning**.
- Web checks (from `apps/web`):
  - `npm run typecheck` → **pass**.
  - `npm run build:clean` → **fail** with persistent `EISDIR` on `node_modules/next/dist/pages/_app.js` after scripted `npm ci` retry.

### Risks / Follow-ups
- **Blocker:** web deterministic clean-build proof remains unresolved due to persistent `EISDIR` failure signature.
- **Blocker:** production alerting for repeated invalid webhook signatures remains an open ops control.
- **Non-blocker:** API auth/session generic denial, event/log payload hygiene, URL safety, diagnostics/output sanitization, and route-level subscription throttling are passing with regression evidence.

## Checkpoint Update (2026-03-03 - Sprint 6 Frontend Execution: Pilot UX + Instrumentation + Interview Artifacts)

### Done
- Executed Sprint 6 frontend implementation pass in `apps/web/src/components/coaching/CoachingProjectWorkbench.tsx`:
  - hardened pilot launch/member gate UX with clearer upgrade messaging and recovery prompts.
  - added live issue response card with explicit retry actions and fallback instructions.
- Added conversion instrumentation module:
  - `apps/web/src/lib/conversion.ts`
  - wired launch/intake/generate/regenerate/export/upgrade/mentoring CTA tracking events.
- Finalized interview-ready artifact UX in project output viewer and exports:
  - new Interview Artifacts tab (STAR stories, portfolio checklist, recruiter mapping).
  - markdown export now includes interview artifact sections.
- Added coach feedback tagging UI to review workflow:
  - selectable feedback tags serialized into `coach_notes` for backend quality loop compatibility.

### Validation
- `npm run typecheck` (apps/web) ❌
  - pre-existing `reactflow` typing import errors (`TS2614`) in model-canvas/editor files.
- `npm run build` (apps/web) ❌
  - `Cannot find module 'styled-jsx/package.json'` from Next runtime loader.
- `npm run build:clean` (apps/web) ❌
  - clean/retry path reproduces same `styled-jsx` missing-module failure.

### Risks / Follow-ups
- Event telemetry is currently local-first (console/localStorage) pending backend analytics ingestion endpoint.
- Feedback tags are notes-serialized until backend contract provides dedicated tag field.

## Checkpoint Update (2026-03-03 - Sprint 6 Backend Execution)

### Done
- Delivered Sprint 6 backend pilot/learning-loop package in coaching APIs.
- Added pilot launch readiness contract endpoint:
  - `GET /coaching/pilot/launch-readiness` (subscription + lifecycle + launch/intake signal checks).
- Added conversion instrumentation persistence and API rollup:
  - new DB table: `coaching_conversion_events`
  - new endpoints: `POST /coaching/mentoring/intent`, `GET /coaching/conversion/funnel`
  - event capture wired into intake, launch-token verify, generate/regenerate, and export paths.
- Added interview-ready package consistency in SOW contract/export:
  - new `interview_ready_package` in `CoachingSowDraft`
  - STAR bullets, portfolio checklist, recruiter mapping consistency checks in validator
  - markdown export now includes interview-ready sections.
- Added coach feedback capture loop:
  - new DB table: `coaching_feedback_events`
  - new endpoint: `POST /coaching/review/feedback`
  - generation pipeline ingests recent coach regeneration hints and merges into diagnostics hints.
- Added observability baseline for generation runs:
  - response/persisted metadata now includes `latency_ms`, `latency_band`, token usage-derived `cost_band`.

### Validation
- Added focused test suite:
  - `apps/api/tests/test_coaching_sprint6_backend.py`

### Risks / Follow-ups
- Conversion metrics are operationally useful but still event-level; weekly aggregation/report job is pending.
- Cost band is estimate proxy (token usage) and should be replaced/augmented with provider billing telemetry for finance-grade tracking.

## Checkpoint Update (2026-03-03 - Sprint 5 Security Execution + Pilot D1 Evidence Draft)

### Done
- Completed Sprint 5 security execution pass focused on deterministic build impact + regression expansion.
- Added auth/session contract regression coverage for protected LLM readiness route:
  - `apps/api/tests/test_auth_contract_security.py` now includes 401 generic contract for `GET /coaching/health/llm-readiness`.
- Expanded URL safety regression set for new Sprint 5 changes:
  - `apps/api/tests/test_llm_output_security.py` now blocks `.local` host payloads (e.g., `https://internal.dev.local/admin`) in generated SOW URL surfaces.
- Closed an output-leak gap in quality diagnostics:
  - `apps/api/coaching.py::build_quality_diagnostics(...)` now secret-masks `top_deficiencies` messages.
  - added regression test proving secret-like strings in deficiency messages are masked before response emission.
- Drafted D1 pilot evidence pack status with explicit blocker/non-blocker separation in Sprint 5 docs/checklists.

### Validation
- Security pack run (from `apps/api`):
  - `python -m pytest -q tests/test_auth_contract_security.py tests/test_llm_output_security.py tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py`
  - Result: **44 passed, 1 warning**.
- API compile check:
  - `python -m compileall -q .` → **pass**.
- Web deterministic verification attempts (from `apps/web`):
  - `npm ci --no-audit --no-fund --verbose` → **pass** (81 packages installed; engine warning on host Node/npm versions)
  - `npm run typecheck` → **pass**
  - `npm run build:clean` → fail with persistent `EISDIR` on `src/app/page.tsx` even after scripted reinstall/retry.

### Risks / Follow-ups
- **Blocker:** cannot yet claim A1 deterministic clean-build acceptance in this host context because `build:clean` still fails with persistent `EISDIR` (`src/app/page.tsx`) after lockfile-faithful recovery retry.
- **Non-blocker:** API security posture for auth/session, URL safety, and output/diagnostics secret masking remains strong and regression-backed.
- Existing production blockers remain: webhook signature verification and route-level rate limiting.

## Checkpoint Update (2026-03-03 - Sprint 5 Backend Reliability + Output Quality Execution)

### Done
- Closed Sprint 5 P0 backend output quality depth improvements:
  - stronger regeneration guidance in `apps/api/coaching.py::build_quality_diagnostics(...)` using structural and milestone-specificity thresholds.
  - added explicit fit-for-sale depth hint when score remains below floor.
- Hardened coach queue action reliability in `apps/api/main.py`:
  - added `_persist_review_state_with_retry(...)` (bounded retry with consistency re-read checks).
  - integrated retry/consistency behavior into `POST /coaching/review/status` and `POST /coaching/review/approve-send`.
  - `approve-send` now blocks when latest run is not `completed`.
  - queue action responses now expose persistence consistency metadata (`persist_attempts`, `persist_ok`).
- Added/updated tests:
  - `apps/api/tests/test_coaching_review_endpoints.py`
    - transient retry recovery path
    - approve-send guard for non-completed runs
  - `apps/api/tests/test_coaching_sprint2_backend.py`
    - review-status response consistency contract assertion.
- API determinism + CI parity command alignment:
  - standardized documented commands to run from `apps/api`:
    - focused: `python -m pytest -q <target files>`
    - full: `python -m pytest -q`

### Validation
- Focused (from `apps/api`):
  - `python -m pytest -q tests/test_coaching_review_endpoints.py tests/test_coaching_sprint2_backend.py tests/test_coaching_llm_contract.py`
- Full (from `apps/api`):
  - `python -m pytest -q`

### Risks / Follow-ups
- Retry helper is endpoint-local and synchronous; consider queue-backed async reconciliation if write contention grows.
- Review status values are still stringly-typed across layers; shared constants/enum contract should be introduced next pass.

## Checkpoint Update (2026-03-03 - Sprint 4 Backend Core Execution)

### Done
- Restored coach-review queue reliability endpoints in `apps/api/main.py`:
  - `POST /coaching/review/approve-send`
  - `POST /coaching/member/launch-token/verify`
- Completed subscription lifecycle hardening for queue/member flow:
  - `GET /coaching/subscription/lifecycle-readiness`
  - idempotent replay handling in `POST /coaching/subscription/sync` using provider `raw_event.id` + `idempotent_replay` contract field.
- Upgraded SOW output quality diagnostics (`apps/api/coaching.py`):
  - added milestone-specificity scoring signal.
  - added targeted regeneration hints and recommended-regeneration guidance.
- Added deterministic pytest config for API package (`apps/api/pytest.ini`).

### Validation
- `apps/api/.venv`: `.venv\\Scripts\\python -m pytest` → **101 passed, 4 skipped, 1 warning**.
- clean environment (`repo/.venv-ci`):
  - `.venv-ci\\Scripts\\python.exe -m pip install -r apps/api/requirements.txt`
  - `..\\..\\.venv-ci\\Scripts\\python.exe -m pytest` (from `apps/api`) → **101 passed, 4 skipped, 1 warning**.

### Risks / Follow-ups
- Launch-token verification is currently signature + binding based; does not yet enforce one-time-use nonce/TTL expiry window.

## Checkpoint Update (2026-03-03 - Sprint 4 Security Pilot Gate Pass)

### Done
- Re-verified generic auth/session denial contracts on updated coaching/auth surfaces and expanded route coverage tests:
  - `apps/api/tests/test_auth_contract_security.py` now exercises additional protected routes for consistent 401 shape.
  - aligned legacy assertion in `apps/api/tests/test_coaching_security_access.py` to current generic 403 subscription contract.
- Hardened generated-output narrative masking:
  - `apps/api/coaching.py::sanitize_generated_sow(...)` now recursively masks secret-like strings inside structured `project_story` payloads.
- Expanded defense-in-depth URL sanitization regression coverage:
  - added parametrized unsafe URL blocking tests for localhost/private and blocked schemes (`data:`, `javascript:`) in `apps/api/tests/test_llm_output_security.py`.
- Added diagnostics secrecy regression:
  - validated `quality.quality_diagnostics` remains provider/secret free and does not expose raw provider payload artifacts.

### Validation
- `python -m pytest -q tests/test_auth_contract_security.py tests/test_llm_output_security.py` (from `apps/api`) ✅
- `python -m pytest -q tests/test_security_sprint2.py tests/test_coaching_security_access.py tests/test_coaching_generation_guardrails.py` (from `apps/api`) ✅

### Risks / Follow-ups
- Frontend stale-auth recovery logic is validated indirectly via backend contract + existing UI behavior; dedicated frontend unit/E2E tests are still recommended.
- Pilot checklist still has open production blockers outside this pass (provider webhook signature verification, route-level rate limiting).

## Checkpoint Update (2026-03-03 - Sprint 4 Frontend Stability + Intake/Diagnostics Pass)

### Done
- Hardened deterministic web build recovery in `apps/web/scripts/build-clean.ps1`:
  - added lockfile requirement check before attempting repair (`package-lock.json` must exist).
  - added explicit Node/npm version guidance output for reproducible local setup.
  - broadened recovery triggers beyond `EISDIR` to include missing local binary/module patterns (`next`/`tsc` not found).
  - switched reinstall path from `npm install` to lockfile-faithful `npm ci --no-audit --no-fund`.
- Improved generation quality card rendering in `CoachingProjectWorkbench`:
  - now displays `structure_score` and `section_order_valid`.
  - now displays explicit `missing_sections` list when returned by backend diagnostics.
  - added actionable “Regenerate guidance” list derived from quality/structure diagnostics to make remediation steps obvious.
- Confirmed intake UX completion remains in place in active form flow:
  - labeled confidence rows for SQL/modeling/orchestration/stakeholder communication.
  - platform/tool exposure checklist with `Other` option and conditional text fields.
  - clarified constraints/support wording with helper guidance.
- Confirmed stale auth/readiness state clear flow remains centralized and invoked after successful protected API calls.

### Validation
- Pending execution in this subagent pass:
  - `npm run typecheck` (from `apps/web`)
  - `npm run build:clean` (from `apps/web`)

### Risks / Follow-ups
- Recovery script cannot fully remediate host-level npm extraction/fs corruption issues; it now handles common deterministic cases and provides clearer operator guidance.
- If product expects `Other` handling in preference-stage stack/tool selectors (not just exposure checklist), add explicit fields and backend mapping in next UX pass.

## Checkpoint Update (2026-03-02 - Frontend Hotfix: Session Banner + Self-Assessment UX)

### Done
- Hardened session-expired banner behavior in `CoachingProjectWorkbench` with a single auth-error handler:
  - added centralized protected-call error mapper (`handleProtectedApiError`) as the single source of auth error truth.
  - all protected API catch paths now route through this helper.
  - session banner + readiness auth residue are cleared on authenticated 2xx responses via `markAuthenticatedApiSuccess()` (including generation/review/detail paths before business-level `ok` checks).
- Updated self-assessment skills confidence controls to include explicit adjacent labels per dropdown (SQL, data modeling, orchestration, stakeholder comms).
- Reworked tools/platform exposure in self-assessment to checkbox lists with `Other` checkbox + conditional free-text input for both platforms and tools.
- Replaced ambiguous constraints/support numeric dropdown with labeled fields + helper copy:
  - hours available per week
  - target timeline in weeks
  - support needed from coach
- Added tighter section spacing and clearer inline labels in the self-assessment cards for faster scanning.

### Validation
- `npm run typecheck` (from `apps/web`) ✅

### Risks / Follow-ups
- "Other" values are currently serialized into formatted self-assessment text for compatibility; move to first-class structured backend fields if downstream analytics/reporting needs object-level parsing.
- Preferences timeline selector still exists in the stack/timeline step; alignment between that selector and self-assessment timeline should be finalized in product UX decisions.

## Checkpoint Update (2026-03-02 - Frontend Sprint 3 Kickoff: Route Split + Build Resilience)

### Done
- Added route-based coaching UX split in Next app router:
  - `/intake` for intake-first flow
  - `/review` for coach queue + submission review workflow
  - `/project/[id]` for project-output-focused view tied to a submission id
  - root `/` now redirects to `/intake`
- Extended `CoachingProjectWorkbench` to support route mode props (`mode`, `projectId`) and conditional section rendering so each route emphasizes the correct workflow while preserving existing feature behavior.
- Added in-app route switcher controls (Intake / Review / Project) for quick navigation across the new route surfaces.
- Added resilient web build recovery script:
  - `apps/web/scripts/build-clean.ps1`
  - clears `.next` and ts build artifacts before build
  - detects `EISDIR` build failures, reinstalls `node_modules`, and retries once.
- Added package script:
  - `npm run build:clean` (apps/web)

### Validation
- Route files + workbench compile shape updated; local environment dependency corruption currently blocks full `typecheck/build` verification in this pass (`tsc` missing from corrupted/incomplete `node_modules`, intermittent npm extract ENOENT on reinstall).
- Added deterministic recovery path via `npm run build:clean` for environments affected by `.next`/node_modules filesystem inconsistency.

### Risks / Follow-ups
- Host environment shows package extraction instability on `apps/web/node_modules` (tar ENOENT during install), which can still block clean verification until filesystem/package install reliability is restored.
- Recommend rerunning in stable local disk context (or after npm cache + fs health cleanup) with:
  - `npm install --no-audit --no-fund`
  - `npm run typecheck`
  - `npm run build:clean`

## Checkpoint Update (2026-03-02 - Sprint 3 Security Execution Kickoff)

### Done
- Verified and expanded auth/session generic denial contract coverage for new/updated routes:
  - added 401 generic contract regression for protected coaching readiness route.
  - added 403 generic contract regressions for role denial and inactive-subscription denial paths.
  - validated denial responses do not leak raw parser/token/role/subscription internals.
- Added defense-in-depth checks for frontend/backend URL policy consistency:
  - frontend `safeExternalUrl` now blocks `::1`, `.local`, and RFC1918/link-local/loopback IPv4 literals in addition to scheme checks.
  - backend URL safety regression now explicitly verifies private IPv4 and IPv6 loopback fetch blocking.
- Expanded generated-output secret masking coverage in backend sanitization:
  - now masks secret-like patterns in `project_title`, `project_story`, `business_outcome` narrative fields, and milestone execution/rationale fields (`execution_plan`, `expected_deliverable`, `business_why`, deliverables entries).
- Updated security checklist with a CI-ready Sprint 3 regression command pack.

### Validation
- `python -m pytest -q tests/test_auth_contract_security.py tests/test_security_sprint2.py tests/test_llm_output_security.py` (from `apps/api`) ✅
- `npm run typecheck` (from `apps/web`) ✅

### Risks / Follow-ups
- Frontend private-host detection remains literal-host based (no DNS resolution in browser); backend remains authoritative for SSRF protection.
- Continue adding allowlist-backed outbound URL policy if production requires stricter domain controls.

## Checkpoint Update (2026-03-02 - Sprint 3 Backend Kickoff: Contract + Workflow + Launch Reliability)

### Done
- Integrated latest backend/security/frontend-linked API behavior into a coherent backend contract pass:
  - review queue endpoint now forwards `status` into DB query (`list_coaching_intake_submissions(..., review_status=status)`) so backend filtering semantics align with frontend status-filter UX contract.
  - stabilized subscription sync contract with explicit replay field (`idempotent_replay`) and deterministic event-id behavior.
- Cleared test environment blocker:
  - added `httpx==0.27.2` to `apps/api/requirements.txt` so `fastapi/starlette` `TestClient` collections run without missing dependency errors.
- Improved source-quality logic for generated SOW data source selection:
  - added deterministic datasource candidate catalog with concrete public URLs + ingestion doc links.
  - implemented `_select_data_sources(...)` to choose sources based on parsed job signals + intake preferences.
  - added mandatory `selection_rationale` support and validator checks (`DATA_SOURCE_RATIONALE_MISSING`).
  - auto-revision now backfills rationale when missing.
- Completed coach workflow approve-send backend scaffold:
  - new endpoint `POST /coaching/review/approve-send` sets review state to `approved_sent` and returns launch handoff payload.
  - includes short-lived signed launch token scaffold (`launch_token`, expiry, launch path) for Squarespace/member flow handoff.
  - new endpoint `POST /coaching/member/launch-token/verify` validates signature/expiry/workspace+submission binding.
- Added Squarespace/member launch readiness reliability checks:
  - new DB helpers for event lookup + recent event listing (`get_coaching_subscription_event`, `list_recent_coaching_subscription_events`).
  - `POST /coaching/subscription/sync` now idempotently handles replayed provider events when event id repeats.
  - new endpoint `GET /coaching/subscription/lifecycle-readiness` returns account/event consistency checks and lifecycle health signals.
- Added/updated backend tests:
  - `tests/test_coaching_llm_contract.py` (datasource quality/rationale coverage)
  - `tests/test_coaching_review_endpoints.py` (approve-send + launch token verify)
  - `tests/test_coaching_subscription.py` (idempotent sync replay + lifecycle readiness)

### Validation
- Added dependency for test collection: `httpx==0.27.2`.
- Targeted API tests executed from `apps/api`:
  - `python -m pytest -q tests/test_coaching_llm_contract.py tests/test_coaching_review_endpoints.py tests/test_coaching_subscription.py`

### Risks / Follow-ups
- Launch token scaffold is HMAC-based and stateless (no one-time-use/JTI replay store yet).
- Subscription lifecycle checks currently compare account status to latest event payload status; full provider-signature verification and durable event-processing state machine still pending.

## Checkpoint Update (2026-03-02 - Security Session/Diagnostics Hardening Pass)

### Done
- Hardened auth/session exception responses for coaching + auth routes:
  - 401/403 now return a consistent generic contract (`ok`, `code`, `auth_required`, `subscription_required`, `message`).
  - removed raw auth detail passthrough for these routes (`Missing bearer token`, `Invalid or expired token`) to reduce internal leakage.
- Added generation diagnostics sanitization before returning/persisting `generation_meta`:
  - now allowlists safe fields (`provider`, `model`, `attempts`, `error_type`, optional `finish_reason`, token usage counts).
  - strips sensitive/internal fields such as provider base URLs, API keys, raw provider payload objects, and non-contract extras.
- Added regression tests for auth banner-reset and diagnostics safety:
  - `tests/test_auth_contract_security.py` verifies generic auth payloads and that a successful call after a 401 does not carry stale auth error flags.
  - `tests/test_llm_output_security.py` now verifies sanitized `generation_meta` is secret-free in both response and persisted validation payload.

### Validation
- `python -m pytest -q tests/test_auth_contract_security.py tests/test_coaching_feedback_pass.py tests/test_llm_output_security.py tests/test_coaching_llm_contract.py` (from `apps/api`) ✅
- `python -m compileall -q .` (from `apps/api`) ✅

### Risks / Follow-ups
- Auth/coaching error messages are intentionally generic; if UX needs route-specific guidance, keep it high-level and avoid exposing token/parser/provider internals.
- Sanitized `generation_meta` is now contract-oriented; if new diagnostic fields are needed later, add explicit allowlist coverage + regression tests before exposing.

## Checkpoint Update (2026-03-02 - Frontend Urgent UX Fix: Session + Readiness + Assessment Redesign)

### Done
- Fixed sticky session-expired UX state in `CoachingProjectWorkbench`:
  - introduced centralized stale-state clear helper (`clearAuthStaleState`) to clear session banner + readiness auth error.
  - now clears auth error state after successful authenticated API calls (submissions, readiness, intake submit, generation success, submission detail load, review save).
  - now also clears state immediately after successful simulated login/subscription activation paths.
- Fixed readiness panel stale-expired behavior:
  - readiness success path now explicitly resets prior error state.
  - successful authenticated calls elsewhere also clear stale readiness auth errors.
- Simplified visible plan/tier clutter while preserving backend feature-gating logic:
  - removed verbose tier pricing/inclusion card and intake tier badges.
  - retained hidden gating behavior (`planTier` state + `canAccessReviewQueue`/`canBookMentoring`) so coach-review/mentoring entitlements still behave correctly.
- Redesigned self-assessment intake into a robust multi-section form aligned to coaching assessment style:
  - Career goals
  - Background + delivery examples
  - Skills confidence (SQL/modeling/orchestration/stakeholder)
  - Tools/platform exposure
  - Portfolio/interview readiness
  - Constraints/support
  - updated structured serialization (`buildStructuredAssessment`) to preserve sectioned output in `self_assessment_text`.

### Validation
- `npm run typecheck` (apps/web) ✅

### Risks / Follow-ups
- `planTier` remains scaffolded local state (default starter); if product wants visible tier management again, reintroduce as compact controls tied to real subscription backend payload.
- Structured assessment is still persisted as formatted text for compatibility; can migrate to backend-native object payload once schema contract is finalized.

## Checkpoint Update (2026-03-02 - Frontend Feedback Pass: Intake UX + Session Handling)

### Done
- Updated coaching workbench intake UX for structured collection:
  - replaced freeform self-assessment textarea with questionnaire fields (career goal, strengths, growth areas, confidence level, weekly commitment, portfolio status).
  - replaced job links textarea with per-line URL inputs (8-row baseline) and inline validation hints for invalid URLs.
  - replaced stack freeform entry with platform/tool checkbox groups and timeline picker.
  - intake submit now composes structured self-assessment text and sends selected platform/tool preferences.
- Added default prefill support from backend recommendations when available on latest generation run (`recommendations.platforms`, `recommendations.tools`, `recommendations.timeline_weeks`).
- Hardened frontend 401/session handling:
  - API client now normalizes 401 responses to `Session expired (401)`.
  - coaching UI catches unauthorized errors and shows a session-expired banner rather than raw error output.
  - request error surfaces now use sanitized user-facing messages.
- Enhanced visual presentation:
  - added brand logo in hero header (`/brand/logo.png`).
  - introduced responsive input grid styling (`.coaching-input-grid`) and tightened spacing.
  - added prominent project output overview card so key sections are visible immediately.

### Validation
- `npm run typecheck` (from `apps/web`) ✅

### Risks / Follow-ups
- Structured questionnaire currently serializes into `self_assessment_text` for compatibility; backend-native object binding can be switched on once full payload contract is finalized.
- Logo render assumes `/brand/logo.png` remains present in web public assets.

## Checkpoint Update (2026-03-02 - Backend Feedback Pass: Intake/Auth/Recommendations)

### Done
- Added explicit coaching auth/subscription guidance payloads for key UX endpoints:
  - `POST /coaching/intake`
  - `GET /coaching/health/readiness`
  - payload shape now includes `code`, `auth_required`, `subscription_required`, and `message` on 401/403.
- Tightened intake payload support for structured job links:
  - new `job_links` entry type supports objects (`{ url, title?, source? }`) in addition to URL strings.
  - actionable validation errors now point to indexed entries (e.g., `job_links[0].url must start with http:// or https://`).
- Added backend intake schema support for Google-form-style structured fields:
  - `self_assessment` object (bounded key set)
  - `stack_preferences[]` and `tool_preferences[]` checkbox arrays
  - these are persisted under `preferences_json` for downstream generation/review.
- Added recommendation endpoint to infer defaults from job links:
  - `POST /coaching/jobs/recommendations`
  - parses job postings and returns top `stack` and `tools` recommendations with scores.
- Added backend tests:
  - `apps/api/tests/test_coaching_feedback_pass.py`
  - updated RBAC tests to account for subscription-gated intake/validate-loop paths.

### Validation
- `python -m pytest -q tests/test_coaching_feedback_pass.py tests/test_rbac_endpoints.py tests/test_coaching_security_access.py` (from `apps/api`) ✅

### Risks / Follow-ups
- Recommendations are deterministic keyword-driven today; consider weighted ranking + explainability metadata per recommendation.
- `self_assessment` currently enforces a fixed key set; expand intentionally if form schema evolves.

## Checkpoint Update (2026-03-02 - Security Feedback Pass)

### Done
- Hardened `CoachingIntakeRequest` validation in `apps/api/main.py`:
  - strict request shape (`extra=forbid`)
  - structured-field bounds on `workspace_id`, `applicant_name`, and `preferences.*`
  - freeform max-length controls for `resume_text` and `self_assessment_text`
  - job-link constraints (`http/https` only, fully-qualified host, max 20 links)
- Tightened subscription denial behavior to avoid leaking internal status strings:
  - `_require_active_coaching_subscription(...)` now returns generic `403 Active coaching subscription required`.
- Added security regression tests in `apps/api/tests/test_coaching_security_access.py` for:
  - unsafe job-link scheme rejection
  - malformed job-link payload rejection
  - oversized freeform field rejection
  - non-leaky subscription denial message assertions
- Added form input validation policy doc:
  - `docs/coaching-project/FORM_INPUT_VALIDATION_POLICY.md`
- Updated checklist docs to include intake form validation controls:
  - `docs/coaching-project/SECURITY_CHECKLIST.md`

### Validation
- `python -m pytest tests/test_coaching_security_access.py -q` (from `apps/api`) ✅
- `python -m compileall main.py` (from `apps/api`) ✅

### Risks / Follow-ups
- Intake URL validation currently enforces scheme + host only; domain allowlists/reputation checks are still out of scope.
- `preferences` currently allows only the known baseline keys; expand intentionally if product adds additional structured inputs.

## Checkpoint Update (2026-03-02 - Coaching Backend Sprint 2 Integration Pass)

### Done
- A1/A2 integration checks executed for backend contract paths and review flow smoke tests.
- B1 implemented provider retry/timeout/failure classification in `generate_sow_with_llm` with attempts/error_type metadata.
- B2 added backend quality scoring (`compute_sow_quality_score`) and regenerate-aware quality delta tracking in generation responses/persistence.
- C1 enforced premium gating across review-detail and review-queue endpoints using active subscription checks.
- D1 added coach notes/status backend workflow support:
  - new intake fields: `coach_review_status`, `coach_notes`
  - endpoint: `POST /coaching/review/status`
  - review queue supports status filtering.
- E1 added backend readiness health signal endpoint: `GET /coaching/health/readiness`.
- Added backend tests for sprint-2 capabilities:
  - `apps/api/tests/test_coaching_sprint2_backend.py`

### Validation
- `python -m pytest -q apps/api/tests/test_coaching_sprint2_backend.py apps/api/tests/test_coaching_review_endpoints.py apps/api/tests/test_coaching_generation_guardrails.py`

### Risks
- Retry/backoff currently retries immediately; jittered backoff can be added for high-volume provider incidents.
- Readiness check validates key presence + LakeBase health; provider live ping is not yet enabled in readiness endpoint.

### Needs from others
- Frontend wiring for coach review status update actions and status filter controls.

### Next
1. Add bounded exponential backoff with jitter for provider retries.
2. Surface quality score/delta and regenerate affordance in coaching UI.
3. Extend readiness endpoint with optional provider reachability probe.

## Checkpoint Update (2026-03-02 - Coaching Backend Sprint 2 Close Pass)

### Done
- **D1 coach notes/status roundtrip completed**
  - `GET /coaching/intake/submissions` now supports optional `status` filter and returns `status_filter` echo.
  - backend storage query path supports `review_status` filtering for both DuckDB and Postgres.
  - list endpoint now enforces active subscription before returning queue data.
- **C1 premium-route gating audit + patch**
  - added active-subscription enforcement for:
    - `POST /coaching/sow/validate`
    - `POST /coaching/sow/validate-loop`
    - `GET /coaching/health/readiness`
  - kept existing review/detail/generate/export gating in place.
- **E1 readiness payload expanded for frontend panel**
  - `GET /coaching/health/readiness` now returns:
    - `api_key_present` (+ backward-compatible `llm_key_present`)
    - `provider_reachable`, `provider_message`, `base_url`
    - `backend_health` (`ok`, `message`) and legacy `lakebase_*` fields
    - unified `ready` signal (`key && provider && backend`).
- **B2 regenerate quality delta metadata hardened**
  - generation response + persisted validation now include `quality.quality_delta_meta` with:
    - `before`: score/findings_count
    - `after`: score/findings_count
    - `score_delta`, `findings_delta`
  - `quality_delta` remains available as score-delta alias.
- Added/updated backend tests for these close items:
  - `apps/api/tests/test_coaching_sprint2_backend.py`
  - `apps/api/tests/test_security_sprint2.py`
  - `apps/api/tests/test_coaching_pass2.py`
  - `apps/api/tests/test_coaching_review_endpoints.py`

### Validation
- `python -m pytest tests/test_coaching_sprint2_backend.py tests/test_security_sprint2.py tests/test_coaching_review_endpoints.py tests/test_coaching_pass2.py -q` (from `apps/api`) ✅
- `python -m compileall main.py db_lakebase.py` (from `apps/api`) ✅

### Risks / Follow-ups
- Readiness provider probe is request-time; if provider is degraded this route can become slower/noisier for UI refresh loops.
- Intake list status filter is exact normalized match; if future states expand, shared enum constants should be introduced.

## Checkpoint Update (2026-03-02 - Coaching Frontend Sprint 2 Integration Pass)

_Update note: closeout wiring + safety/readiness pass completed in frontend subagent run (2026-03-02 14:xx EST)._ 

### Done
- Completed frontend closeout pass for remaining Sprint 2 coaching items in `CoachingProjectWorkbench`.
- **D1 coach ops backend wiring:**
  - wired coach review save action to `POST /coaching/review/status`
  - loaded existing `coach_review_status` + `coach_notes` from submission detail endpoint
  - added queue status filter control using backend status filter via `GET /coaching/review/open-submissions?status=...`
- **B2/B3 output transparency:**
  - surfaced fallback explanation text when scaffold fallback is used
  - surfaced quality score/band and regenerate delta details (before→after)
  - passed `regenerate_with_improvements` flag in generation requests
- **E1 readiness panel:**
  - added frontend readiness health card wired to `GET /coaching/health/readiness`
  - includes refresh action and key readiness signals (LLM key, LakeBase health)
- **Security UX hardening:**
  - added frontend safe-link guard for rendered links (job links, data sources, resource links)
  - blocked/unsafe links now render warning badges instead of clickable anchors
- Extended frontend API client (`apps/web/src/lib/api.ts`) with typed methods/contracts for:
  - `POST /coaching/review/status`
  - `GET /coaching/health/readiness`
  - `GET /coaching/review/open-submissions` (status filter + typed review status payload)
  - `POST /coaching/sow/generate` (`regenerate_with_improvements` request + `quality` response)

### Validation
- `npm run typecheck` (apps/web) ✅
- `npm run build` (apps/web) ✅ (after clean reset of `.next`)

### Risks
- Readiness endpoint currently checks key presence + LakeBase health only (no provider live ping yet).

### Next
1. Add optional provider reachability probe to readiness endpoint.
2. Add richer quality telemetry rollups in UI (trend over runs).
3. Normalize timeline events for review status updates as first-class timeline entries.

## Scope
POC for AI Data Modeling IDE with:
- blast-radius analysis
- configurable governance/rules
- secure collaboration
- demo-ready UX and integration hooks

---

## Executive Summary
The POC has moved from baseline editor + APIs into a working governance workflow:
- customer-configurable connections (including Databricks UC)
- standards/regulatory document + template flow
- findings lifecycle with audit trail
- PR summary + webhook/provider comment integrations
- run history and export/reporting UX

Core platform value is now demonstrable end-to-end. Remaining work is primarily production-hardening, deeper ingestion, and CI/CD automation.

---

## Completed (Implemented)

### 1) Core Modeling + Validation/Impact
- Visual ERD editor (nodes/relationships) with AST import/export.
- Deterministic and probabilistic validation/impact paths.
- Run persistence for validation and impact results.
- Canvas version persistence.

### 2) Platform Data + Bootstrap
- DuckDB bootstrap for core app tables.
- Bootstrap health/status endpoint + UI panel.
- Contract parity hardening (camelCase/snake_case support).

### 3) Auth + Access Foundations
- Login/auth baseline with hashed password handling.
- Role checks on protected endpoints.
- Session controls scaffolding (`/auth/logout`, `/auth/session-stats`).
- Admin user lifecycle endpoints (`/admin/users`).

### 4) Connections (Customer-Configurable)
- Workspace-level connection settings for:
  - Databricks/Unity Catalog
  - information_schema
  - Git
  - Power BI
- Databricks UC supports:
  - `connection_string` OR `host + token`
  - `profile_name`, `http_path`, warehouse/catalog/schema fields
- Databricks validation endpoint with optional live test:
  - `POST /connections/validate/databricks-uc`
- Sensitive fields redacted on read:
  - token, connection string, DB password, Power BI client secret

### 5) Standards/Regulatory Foundations
- Template seed files and templates API.
- Standards/regulatory policy document upload.
- Chunking + retrieval scaffold for uploaded policy docs.
- Standards evaluation endpoint with traceable findings (`source_ref`, excerpts).
- Workspace-level template version pinning:
  - `workspace_policy_config`
  - `/standards/policy-config` GET/POST

### 6) Findings Lifecycle + Governance Ops
- Single finding status update endpoint.
- Bulk finding status update endpoint.
- Supported statuses:
  - open
  - accepted-risk
  - remediated
  - false-positive
- Audit trail persistence for status transitions:
  - `finding_status_audit`
  - `/standards/finding-status/audit`

### 7) Reporting + Integration
- Run history endpoint and UI panel.
- Findings + run history export (JSON/CSV).
- Copy report summary and copy PR summary UX.
- PR summary generation endpoint (`/reports/pr-summary`).
- Generic webhook posting (`/reports/pr-webhook`).
- Provider-specific PR/MR comment posting (`/reports/pr-comment`) for:
  - GitHub
  - GitLab
- UI support for provider-specific PR comment posting.

### 8) UX / Demo Improvements
- Theme system (dark premium / clean enterprise).
- Presenter/demo scripting controls.
- Table text contrast improvements in ERD node cards for readability.

### 9) Security Hardening (POC-Level)
- Encrypted-at-rest scaffold for sensitive connection fields using `CONNECTION_SECRET_KEY` and `enc:v1:*` envelope format.
- Backward compatibility with existing plaintext rows.

---

## In Progress / Partially Complete
1. Blast-radius expansion to richer dependency ingestion (pipelines/notebooks/Power BI) beyond manual mapping and base scaffolding.
2. Standards/regulatory parser maturity (more robust rule extraction and richer retrieval-backed checks).
3. Production-level auth/session architecture (persistent session/JWT lifecycle hardening).
4. CI/CD automation for PR summary posting (currently manual/API-triggered).

---

## Outstanding (POC-to-Production Gap)

### A) Security + Secrets
- Replace POC encryption method with production-grade crypto (AES-GCM/Fernet).
- Add key rotation strategy and migration path.
- Optional: move secrets to external secret manager adapter (Vault / AWS / Azure).

### B) Blast Radius Depth
- Automated ingestion adapters for:
  - Databricks pipelines/notebooks lineage
  - Power BI datasets/reports lineage
- Confidence/source explanation model improvements in UI.

### C) Governance Workflow Maturity
- Finding ownership, due dates, and SLA-like states.
- Better status note workflows and remediation tracking.
- Audit filtering/pagination at scale.

### D) CI/CD Integration
- Auto-post PR summary during pipelines.
- Retry/queue behavior for outbound comment posting.
- Provider-specific response handling and diagnostics.

### E) Test Coverage
- More endpoint integration tests for report/comment/lifecycle paths.
- E2E UI checks for standards findings lifecycle and PR posting UX.

---

## Suggested Next Sprint Plan (Execution Order)

## Sprint 1 (P0: Security + Reliability)
Goal: close immediate risk and stability gaps.

1. Crypto hardening
- Implement AES-GCM/Fernet encryption utility.
- Support dual-read for `enc:v1` -> `enc:v2` migration.
- Add rotation-ready key config structure.

2. Lifecycle audit usability
- Add audit filters: status, actor, date range.
- Add pagination (server + UI).

3. Test additions
- Add focused tests for:
  - connection secret encrypt/decrypt/read-redaction flow
  - finding-status/bulk/audit endpoints
  - provider comment endpoint validation paths

Deliverable: “secure and supportable governance baseline.”

## Sprint 2 (P1: Integration Automation)
Goal: reduce manual operations and improve developer workflow.

1. CI/CD auto-post mode
- Add endpoint and payload contract for pipeline-triggered PR summary post.
- Add idempotency key support to avoid duplicate comments.

2. Provider adapter hardening
- GitHub/GitLab error mapping and user-friendly diagnostics.
- Add dry-run mode for integration testing.

3. Operational visibility
- Add lightweight integration event log for outbound posting attempts.

Deliverable: “hands-off PR governance comment flow.”

## Sprint 3 (P1/P2: Blast Radius + Governance Intelligence)
Goal: improve analytical depth and decision quality.

1. Dependency ingest adapters
- Normalize external lineage sources into canonical dependency model.

2. Findings enrichment
- Add stronger source attribution and confidence explanation.
- Optional ownership/triage metadata.

3. Demo orchestration polish
- One-click seeded scenario + fallback/degraded mode behavior.

Deliverable: “enterprise-quality demo and stronger impact fidelity.”

---

## Recommendations (Forward-Looking)
1. Add a workspace readiness report endpoint:
   - connectors configured, template pinning status, last runs, unresolved HIGH findings.
2. Add feature flags per workspace for staged rollout of integrations.
3. Add remediation ticket hooks (Jira/ServiceNow) for HIGH findings.
4. Introduce scheduled background sync jobs for lineage ingestion.
5. Add structured telemetry for connector health and PR posting outcomes.

---

## API Areas Now Available for QA/UAT
- `/connections/*`
- `/standards/*`
- `/impact/mappings`
- `/runs/history`
- `/reports/pr-summary`
- `/reports/pr-webhook`
- `/reports/pr-comment`
- `/auth/*`
- `/admin/users`

---

## Immediate Next Build Actions (Queued)
1. Upgrade connection secret crypto from POC envelope to production-grade scheme.
2. Add audit filtering/pagination in backend + UI.
3. Add CI pipeline trigger path for automatic PR summary posting.
4. Expand integration tests for newest standards/reporting/lifecycle endpoints.

## Latest Update (2026-02-24 - UX + GitHub Artifact Flow)
- Improved findings status UX with optimistic state updates so status changes reflect immediately in the UI.
- Updated status option labels to clearer wording (e.g., "accept risk").
- Added GitHub artifact publishing endpoint (`POST /reports/github-artifacts`) to write:
  - AST JSON
  - findings JSON
  into the target GitHub repo/branch/path via GitHub Contents API.
- Added UI action for GitHub mode: **Post AST + Findings to GitHub** with configurable artifact path.

## Latest Update (2026-02-24 - Databricks Schema Ingestion)
- Added backend endpoint: `POST /connections/sync/databricks-schema`
  - Uses workspace Databricks connection settings.
  - Queries Unity Catalog information schema tables + columns.
  - Maps Databricks types into canvas-supported data types.
  - Returns AST payload ready for UI rendering.
- Added Databricks client helpers for settings-based SQL queries and information schema fetches.
- Added frontend API method: `syncDatabricksSchema(...)`.
- Added UI action in Databricks connection section: **Import Databricks Tables/Fields**.
  - Imports schema objects into canvas nodes (tables + fields) for immediate modeling.
- This unlocks blast-radius analysis on real imported customer metadata (vs only manual canvas objects).

## Latest Update (2026-02-26 - Sprint Continuation, Single-Agent)
- Added P0 backend support for finding audit filters + pagination:
  - `GET /standards/finding-status/audit` now supports `page`, `page_size`, `status`, `updated_by`, `date_from`, `date_to`.
  - Response now includes `meta` block with `total`, `page`, `page_size`, `has_more`.
- Updated frontend API client to call new audit query parameters.
- Kept current UI behavior wired to first-page audit fetch while preserving compatibility.
- Validation: API compile pass + web typecheck pass.

## Latest Update (2026-02-27 - Wedge Plan Execution Start)
- Added competitive battlecard doc: `docs/COMPETITIVE_BATTLECARD.md`.
- Added demo execution task plan: `docs/DEMO_READINESS_TASKS.md`.
- Implemented demo readiness backend endpoint:
  - `GET /demo/readiness?workspace_id=...`
  - Returns readiness flag, summary counts, and blockers.
- Added frontend API + sidebar UI card to run and display demo readiness checks.
- This creates a practical gate for “can we demo this flow end-to-end now?”.

## Latest Update (2026-02-27 - Coaching Wedge UX Pass)
- Relationship editor upgraded from CSV join input to explicit join pair rows:
  - add/remove join pairs
  - supports composite joins more reliably for learning and real ERD use.
- Added lesson prompts for Star/Galaxy/Snowflake demo presets.
- Added one-click **Run Full Coaching Exercise** flow to execute:
  - AI suggestions
  - deterministic validation
  - deterministic impact
  - standards evaluation
  - run history/audit/demo readiness refresh.
- This reduces manual steps and hardens the coaching/demo path end-to-end.

## Latest Update (2026-03-01 - Coaching Security Baseline, Items 1-3)
- Added baseline file-handling guardrails for coaching resume intake:
  - extension/content-type/size checks
  - safe filename normalization and storage path construction
  - endpoint: `POST /coaching/intake/resume/validate`
- Added reusable secret/PII masking helpers in API security module:
  - text masking for bearer/token/password/client_secret/api_key patterns
  - nested payload masking utility for structured responses
  - PII hit helper (`email`, `ssn`, `phone`) for regression/security checks
- Upgraded connection settings redaction path to use shared masking utility.
- Added security checklist documentation for coaching workstream:
  - `docs/coaching-project/SECURITY_CHECKLIST.md`
- Added test coverage + regression stubs:
  - `apps/api/tests/test_security_baseline.py`
  - `apps/api/tests/test_security_regression_stubs.py`

## Latest Update (2026-03-01 - Coaching Backend Workstream Items 1-4)
- Implemented **coaching intake persistence** scaffold:
  - New backend endpoint: `POST /coaching/intake`
  - New persistence table: `coaching_intake_submissions`
- Implemented **job posting parsing pipeline scaffold**:
  - New backend endpoint: `POST /coaching/jobs/parse`
  - URL fetch + HTML text extraction + heuristic skills/tools/domain signal extraction
  - New parse cache table: `coaching_job_parse_cache`
- Implemented **SOW generation schema endpoint scaffold**:
  - New backend endpoint: `POST /coaching/sow/generate`
  - Returns structured SOW JSON skeleton and required sections metadata
- Implemented **validation + revision loop skeleton**:
  - New backend endpoint: `POST /coaching/sow/validate-loop`
  - Rule checks for required sections, medallion completeness, milestone minimum, ROI requirements, and resource links
  - Auto-revise-once path if checks fail
  - New generation run persistence table: `coaching_generation_runs`
- Added LakeBase bootstrap + status coverage for new coaching tables.

## Latest Update (2026-03-01 - Coaching Project Creation Frontend Scaffolds)
- Implemented **multi-step coaching intake UX scaffold** in web app sidebar:
  - step navigation for resume, self-assessment, job links, and stack/timeline preferences
  - completion tracking across intake steps
  - draft fields for candidate identity and role targeting
- Implemented **project output viewer scaffold** with section tabs:
  - overview (candidate snapshot + business outcome)
  - milestones (deliverables by phase)
  - architecture (bronze/silver/gold framing)
  - ROI requirements checklist
- Added local scaffold generation flow (`Build Project Scaffold`) to connect intake draft inputs to a structured output preview component.

## Latest Update (2026-03-01 - Coaching Frontend Pass 2 Checkpoint)
- **Done**
  - Added backend coach review list endpoint: `GET /coaching/intake/submissions`.
  - Added web API client methods/types for coaching intake submit + submissions list.
  - Built coach review queue table in `CoachingProjectWorkbench` using backend list endpoint.
  - Added generation stage badges: **Intake Parsed**, **SOW Generated**, **Validated**.
  - Enhanced output viewer with **Recommended Resources** and **Mentoring CTA/Pricing** block.
  - Added student package export actions for **Markdown** and **JSON** download.
- **Validation**
  - `npm install --no-audit --no-fund` (apps/web)
  - `npm run typecheck` (apps/web) ✅
- **Risks**
  - Stage badges are currently UI-driven flags; not yet synchronized to persisted generation run state.
  - Mentoring CTA button is presentational only; booking flow integration is pending.
- **Needs**
  - Optional backend endpoint to load latest generation run per submission for fully server-backed stage status.
  - Product decision on final pricing copy + booking URL.
- **Next**
  - Wire status badges to persisted generation records (`coaching_generation_runs`).
  - Add row action from review queue to load selected submission into the workbench.
  - Add export confirmation toast + test coverage for download helpers.

## Checkpoint Update (2026-03-01 - Coaching Backend Pass 2)

### Done
- Added structured SOW model (`CoachingSowDraft` + `SowMilestone`) and new validation endpoint:
  - `POST /coaching/sow/validate`
- Added SOW draft alias endpoint for explicit generation step:
  - `POST /coaching/sow/generate-draft`
- Added intake review retrieval APIs for coaches:
  - `GET /coaching/intake/submissions`
  - `GET /coaching/intake/submissions/{submission_id}` (includes latest generation run snapshot)
- Added resource matching baseline service wired to `docs/coaching-project/RESOURCE_LIBRARY.json`:
  - `POST /coaching/resources/match`
  - baseline milestone-tag/topic matching + score-based resource tiering
- Added demo-safe seeded package endpoints:
  - `POST /coaching/demo/seed-package`
  - `GET /coaching/demo/seed-package`
  - returns fully composed intake + parsed signals + SOW + validation + resource/mentoring package
- Added backend persistence helpers for pass-2 workflow:
  - `list_coaching_intake_submissions(...)`
  - `get_latest_coaching_generation_run(...)`
- Added API tests for pass-2 coaching path:
  - `apps/api/tests/test_coaching_pass2.py`

### Validation
- `python -m compileall apps/api`
- `python -m pytest apps/api/tests/test_coaching_pass2.py`

### Risks
- Resource matching is intentionally baseline and rules-based; no semantic ranking/embedding relevance yet.
- Demo seed uses static sample job signals for safety/repeatability, not live fetch.

### Needs
- Frontend wiring for new pass-2 endpoints (`/coaching/sow/validate`, `/coaching/resources/match`, seed package APIs).
- Coach dashboard pagination/filtering for larger submission volumes.

### Next
- Add deterministic mentoring tier recommendation rubric (scorecard over skill gaps/timeline).
- Extend resource matching with weighted tags + optional semantic rerank.
- Add one-click endpoint to persist generated seed package as a demo project artifact.

## Latest Update (2026-03-01 - Coaching Security Pass 3: Member Access Threats + Token Misuse)

### Done
- Added hosted app/member access threat model document:
  - `docs/coaching-project/HOSTED_APP_MEMBER_FLOW_THREAT_MODEL.md`
- Added subscription access-check scaffold endpoint with explicit role guard:
  - `POST /coaching/subscription/status`
- Added PII-safe structured logging helpers for auth/subscription paths in `apps/api/security.py`:
  - `pii_safe_auth_log_payload(...)`
  - `pii_safe_subscription_log_payload(...)`
- Applied PII-safe logging in `apps/api/main.py` for:
  - `POST /auth/login`
  - `POST /auth/refresh`
  - `POST /coaching/subscription/status`
- Added security-focused regression tests for unauthorized access/token misuse and safe logging:
  - `apps/api/tests/test_coaching_security_access.py`

### Validation
- `python -m pytest -q apps/api/tests/test_coaching_security_access.py apps/api/tests/test_security_baseline.py`
- `python -m compileall apps/api`

### Risks
- Subscription status endpoint is currently scaffold-only and not yet backed by provider-signed webhook truth.
- Session lifecycle remains in-memory; does not yet provide production-grade revocation/audit durability.

### Needs
- Signed webhook ingestion + server-owned subscription state table for authoritative access checks.
- Short-TTL signed launch token (`jti` replay protection) for Squarespace handoff flow.
- Global log sanitizer middleware to enforce masking invariants beyond endpoint discipline.

### Next
1. Wire subscription status checks to webhook-driven persisted account state.
2. Implement signed launch token verification and replay defense.
3. Add auth/subscription endpoint rate limiting and lockout thresholds.

## Latest Update (2026-03-01 - Coaching Security Pass 2)

### Checkpoint
- **Done**
  - Added PII-safe logging helper utilities in `apps/api/security.py`:
    - `pii_safe_text_summary(...)`
    - `pii_safe_coaching_log_payload(...)`
  - Applied PII-safe structured logging on coaching intake/generation paths in `apps/api/main.py`:
    - `POST /coaching/intake`
    - `POST /coaching/jobs/parse`
    - `POST /coaching/sow/generate`
    - `POST /coaching/sow/validate-loop`
  - Added endpoint-level RBAC coverage for coaching endpoints in `apps/api/tests/test_rbac_endpoints.py`.
  - Added upload threat-guard documentation: `docs/coaching-project/FILE_UPLOAD_THREAT_GUARD.md`.
  - Added malicious content-type/oversize test stubs in `apps/api/tests/test_security_regression_stubs.py`.
  - Added affiliate disclosure + trust language in generated SOW outputs (`apps/api/coaching.py`) and validation checks:
    - `AFFILIATE_DISCLOSURE_MISSING`
    - `TRUST_LANGUAGE_MISSING`
  - Added tests for security-note fields in generated outputs: `apps/api/tests/test_coaching_security_notes.py`.

- **Validation**
  - `python -m pytest -q apps/api/tests/test_security_baseline.py apps/api/tests/test_coaching_security_notes.py apps/api/tests/test_rbac_endpoints.py apps/api/tests/test_security_regression_stubs.py`
    - Result: `25 passed, 4 skipped`.
  - `python -m compileall apps/api`
    - Result: success.

- **Risks**
  - Logging safety currently depends on endpoint discipline (manual usage of safe helper), not a global log-filter middleware.
  - Multipart/byte-level MIME validation and malware scanning are still pending.

- **Needs**
  - Centralized logging sanitizer/filter applied to all API handlers.
  - Real multipart upload endpoint with byte-level MIME sniffing and stream-based size guards.

- **Next**
  1. Add middleware/log filter to enforce masking invariants regardless of endpoint code.
  2. Implement multipart resume upload with MIME sniffing + malware scan hook.
  3. Add end-to-end regression proving raw resume/job text never appears in logs/exports.

## Checkpoint Update (2026-03-01 - Coaching Frontend Pass 3: Squarespace Journey States)

### Done
- Added explicit **coaching auth/subscription gate UI states** in `CoachingProjectWorkbench`:
  - auth state scaffold (`signedOut` / `authenticated`)
  - subscription scaffold (`unknown` / `inactive` / `active`)
  - gated workbench rendering when subscription is inactive or auth missing
- Added **member launch/landing flow scaffold** for Squarespace handoff simulation:
  - launch stages (`memberHome` -> `launchRequested` -> `handoffPending` -> `landed`)
  - launch terms acceptance toggle and contextual state guidance copy
- Added **plan/tier display and upgrade prompt placement** in workbench:
  - tier card with included features and monthly pricing
  - in-flow upgrade CTA for Starter/Pro users
  - active plan badge surfaced inside the coaching intake area

### Validation
- `npm run typecheck` (apps/web) ✅

### Risks
- Auth/subscription/launch states are frontend scaffolds and not yet wired to backend identity/subscription endpoints.
- Upgrade CTA currently updates local UI state only (no checkout/billing handoff URL).

### Needs
- Backend subscription status endpoint and launch token verification endpoint for server-backed gate decisions.
- Product decision for final plan names/pricing copy and billing upgrade destination.

### Next
1. Wire gate state to persisted account/subscription data from backend.
2. Replace simulated launch flow with real Squarespace launch token handoff + verification.
3. Connect upgrade CTA to billing/mentoring booking flow.

## Checkpoint Update (2026-03-01 - Squarespace Subscription Backend Scaffold)

### Done
- Added coaching account/subscription data scaffold in `apps/api/db_lakebase.py`:
  - `coaching_accounts` table for member subscription state (`email`, `plan_tier`, `subscription_status`, `renewal_date`, provider IDs/source).
  - `coaching_subscription_events` table for webhook/sync event intake history.
- Added persistence helpers:
  - `upsert_coaching_account_subscription(...)`
  - `get_coaching_account_subscription(...)`
  - `save_coaching_subscription_event(...)`
- Added subscription endpoints in `apps/api/main.py`:
  - `GET /coaching/subscription/status` (session-aware status lookup + normalized active flag)
  - `POST /coaching/subscription/sync` (Squarespace/Stripe webhook-sync stub to persist event + update account state)
- Added normalized subscription status mapping (`active`, `past_due`, `inactive`, `unknown`) for provider-status compatibility.
- Tightened coaching read-route guards to use session + role assertions (`admin/editor/viewer`) for:
  - `GET /coaching/intake/submissions`
  - `GET /coaching/intake/submissions/{submission_id}`
  - `GET /coaching/demo/seed-package`
- Added tests for new subscription flow:
  - `apps/api/tests/test_coaching_subscription.py`

### Validation
- `python -m pytest tests/test_coaching_subscription.py tests/test_coaching_pass2.py tests/test_rbac_endpoints.py -q` (run from `apps/api`)
  - Result: `19 passed`.

### Risks
- Webhook ingestion is currently a trusted stub; signature verification for Squarespace/Stripe webhook authenticity is not implemented yet.
- Subscription enforcement on all coaching execution routes is not globally required yet (status endpoint + sync path are now available for progressive rollout).

### Needs
- Provider webhook signature validation (Stripe-Signature / Squarespace equivalent) and replay protection.
- Product decision on enforcement mode: hard-block inactive users vs grace-period behavior for `past_due`.

### Next
1. Add verified webhook signature validation and event idempotency checks.
2. Wire account linking from app user/session to subscription record (`username`↔`email`) for deterministic gating.
3. Enable subscription-required guard on selected coaching generation routes once frontend member flow is connected.

## Checkpoint Update (2026-03-01 - Coaching Backend Next-Step Integration)

### Done
- Normalized coaching backend flow by making `/coaching/sow/generate` do full guarded generation:
  - requires active coaching subscription
  - applies one-pass auto-revision guardrail when initial findings exist
  - enforces strict SOW schema (`CoachingSowDraft`) before returning payload
  - persists generation run metadata with guardrail flags for review/audit
- Tightened auto-revision behavior in `coaching.py` so empty `resource_plan.required` is backfilled (not only missing keys).
- Added subscription-gated export endpoint:
  - `POST /coaching/sow/export` (`markdown` or `json` payload rendering)
- Added coach review retrieval endpoints for frontend open-submission actions:
  - `GET /coaching/review/open-submissions`
  - `GET /coaching/review/submissions/{submission_id}/runs`
- Added backend persistence helper for coach review run history:
  - `list_coaching_generation_runs(...)`
- Added tests for new behavior:
  - `apps/api/tests/test_coaching_generation_guardrails.py`
  - `apps/api/tests/test_coaching_review_endpoints.py`

### Validation
- `python -m compileall apps/api`
- `python -m pytest -q` (from `apps/api`)
  - Result: `56 passed, 4 skipped`

### Risks
- Subscription check currently trusts internal account status table; provider signature verification + replay defense still pending.
- `open-submissions` uses latest run status only; future multi-stage review semantics may require explicit state model.

### Needs
- Frontend wiring to new review/export endpoints and subscription-gated response handling.
- Product decision on error UX for inactive subscriptions (upgrade prompt vs support flow).

### Next
1. Add provider-signed webhook verification and idempotent event processing.
2. Add pagination/filter parameters on review endpoints for larger coach queues.
3. Add export artifact persistence option tied to generation run IDs.

## Checkpoint Update (2026-03-01 - Coaching Frontend Pass 4: Review Detail + Gating + Export UX)

### Done
- Integrated **coach review queue action flow** in `CoachingProjectWorkbench`:
  - Added row-level **Open submission** action.
  - Added submission detail panel backed by `GET /coaching/intake/submissions/{submission_id}` via new web client method.
  - Added **Load into intake form** action to hydrate draft fields from selected submission.
- Extended **subscription/plan gating UX** inside workbench:
  - Starter users now see explicit gating for coach review queue access (Pro+ required).
  - Mentoring booking CTA now reflects tier entitlement (Elite required vs enabled).
  - Plan card now surfaces feature unlock badges for review queue + mentoring booking.
- Polished **output viewer resources + mentoring recommendation** section:
  - Clear split between recommended resources and mentoring recommendation block.
  - Added cleaner CTA state messaging when mentoring is locked by tier.
- Added **final package export UX status states**:
  - Markdown/JSON export buttons now show exporting/success/error feedback badges/messages.
  - Export actions remain in-place and now provide immediate user-facing status.
- Extended frontend API contracts in `apps/web/src/lib/api.ts`:
  - Added `CoachingIntakeSubmissionDetail` + `CoachingIntakeSubmissionDetailResult` types.
  - Added `coachingIntakeSubmissionDetail(submissionId)` client method.

### Validation
- `npm run typecheck` (apps/web) ✅

### Risks
- Export status feedback is component-local (no toast system/global notification bus yet).
- Mentoring booking button remains scaffolded (no booking URL workflow wired yet).

### Next
1. Wire review detail panel to generation-run status visualization from `latest_generation_run` (stage badges from server truth).
2. Add pagination/filtering on review queue once larger submission volume is expected.
3. Optionally centralize export feedback into shared toast/notification UX.

## Checkpoint Update (2026-03-02 - Coaching Frontend Pass 5: Premium Output Viewer)

### Done
- Upgraded `CoachingProjectWorkbench` project output viewer from scaffold tabs to **client-facing structured sections**:
  - Executive Summary
  - Data Sources (with links/docs)
  - Architecture
  - Milestones
  - Story Narrative
  - ROI Dashboard Requirements
  - Resource Links by Step
- Enriched generated scaffold payload shape (`ProjectScaffold`) so exports and UI stay aligned:
  - Added `executiveSummary`, `dataSources`, `storyNarrative`, and `resourceLinksByStep`.
  - Kept existing mentoring/recommended resources while introducing per-step resources.
- Added explicit **quality badges** in viewer to surface output completeness:
  - has data source links
  - has ROI requirements
  - resources mapped per milestone
  - executive summary present
  - story narrative included
- Improved readability/layout for client handoff:
  - Card-based section rendering with clearer spacing/hierarchy
  - Better visual separation of summary vs technical detail blocks
  - Premium-style section navigation labels matching SOW language
- Updated Markdown export content to match richer viewer structure and section names.
- JSON export remains direct from enriched scaffold object, preserving parity with UI/markdown.

### Validation
- `npm run typecheck` (apps/web) ✅

### Risks
- Data source and resource link generation is currently scaffolded/static logic (not yet model-derived from backend SOW sections).
- Viewer styling remains inline/component-local; could be moved to shared design tokens for consistency across future pages.

### Next
1. Pull section content from backend-generated SOW contract instead of local scaffold defaults.
2. Add frontend tests for quality badge derivation and markdown export section integrity.
3. Add visual regression snapshots for premium output viewer presentation.

## Checkpoint 2026-03-01 (Security next-step pass)

### Delivered
- Verified and tightened PII-safe logging coverage for newly added subscription/auth flows:
  - Added structured PII-safe logging on `GET /coaching/subscription/status` lookups.
  - Added structured PII-safe logging on `POST /coaching/subscription/sync` ingestion.
- Added server-side subscription enforcement for generation routes:
  - New `_require_active_subscription(...)` guard in `apps/api/main.py`.
  - Applied guard in `POST /coaching/sow/generate` (and transitively `generate-draft`).
- Added regression tests covering:
  - masked email/token behavior for subscription sync/status logging,
  - inactive-subscription denial for generation and generate-draft endpoints.
- Added pilot-ready hardening runbook:
  - `docs/coaching-project/PILOT_RELEASE_HARDENING_CHECKLIST.md`

### Verification
- API tests: `python -m pytest tests/test_coaching_security_access.py tests/test_coaching_subscription.py tests/test_rbac_endpoints.py -q` (from `apps/api`)
- Web compile/build: `npm run build` (from `apps/web`)

### Remaining before pilot go-live
1. Enforce provider webhook signature verification + replay/idempotency controls.
2. Add route-level rate limiting for auth/subscription endpoints.
3. Complete deterministic account linking (`session.username` ↔ subscription email identity).

## Checkpoint 2026-03-02 (Security LLM output guardrails pass)

_Status refresh: checkpoint finalized with tests + docs updates in this pass._

### Delivered
- Hardened probabilistic/LLM integration behavior for missing API keys in `apps/api/services.py`:
  - Added explicit env-key presence guard (`OPENAI_API_KEY` / `LLM_API_KEY`).
  - `run_probabilistic_validation` now emits a safe low-severity `LLM_API_KEY_MISSING` finding instead of silently assuming LLM readiness.
  - `run_probabilistic_impact` now fails safe with empty dependency output when key is absent.
- Added generated-output sanitization utilities in `apps/api/coaching.py`:
  - New `sanitize_generated_sow(...)` and URL safety validator.
  - Blocks/flags unsafe URL schemes (`javascript:`, `data:`) in `resource_plan.*[].url` and `mentoring_cta.program_url`.
  - Masks secret-like patterns in generated narrative fields before they are returned/exported.
- Applied sanitization in API routes (`apps/api/main.py`) so user-provided/generated SOW payloads are sanitized on:
  - `/coaching/sow/generate`
  - `/coaching/sow/validate`
  - `/coaching/sow/validate-loop`
  - `/coaching/sow/export`
- Added regression coverage:
  - New `apps/api/tests/test_llm_output_security.py` for:
    - missing LLM API key behavior,
    - unsafe URL blocking/flagging,
    - secret-like string masking in response payloads.
- Updated pilot/security docs:
  - `docs/coaching-project/PILOT_RELEASE_HARDENING_CHECKLIST.md`
  - `docs/coaching-project/SECURITY_CHECKLIST.md`

### Validation
- `python -m pytest tests/test_llm_output_security.py tests/test_coaching_generation_guardrails.py tests/test_security_baseline.py -q` (from `apps/api`)

### Risks
- Current LLM guard checks key presence only; no provider-specific key format validation yet.
- URL sanitization is scheme/host level and does not yet perform allowlist/domain reputation checks.

### Next
1. Add provider-specific key validation + startup health warning endpoint for LLM readiness.
2. Add shared URL-safe renderer utility on frontend to enforce same denylist before clickable rendering.
3. Add strict typed schema for generated resources/URLs to reduce free-form output risk.

## Checkpoint 2026-03-02 (Backend LLM SOW generation pass)

### Done
- Integrated OpenAI-compatible provider generation path for coaching SOW output:
  - Added `generate_sow_with_llm(...)` in `apps/api/coaching.py`.
  - Reads env config (`OPENAI_API_KEY`, `OPENAI_BASE_URL`, `COACHING_SOW_LLM_MODEL`) and calls `/chat/completions`.
  - Added safe JSON parsing and fallback scaffold behavior when provider is unavailable/fails.
- Upgraded SOW contract + validator guardrails:
  - Enforced required `project_story` section.
  - Enforced `business_outcome.data_sources[*].url` and `ingestion_doc_url` as real non-placeholder links.
  - Enforced milestone-level `resources` links (resources per step).
  - Added URL quality checks for `resource_plan` links.
- Updated generation endpoint (`POST /coaching/sow/generate`):
  - Uses LLM output first, validates strict contract, and runs one auto-revision pass if fields are missing.
  - Persists generation metadata + quality flags in `validation_json` via `save_coaching_generation_run(...)`.
  - Returns `generation_meta` and `quality_flags` in API response.
- Expanded SOW model contract:
  - Added `project_story` to `CoachingSowDraft`.
  - Added milestone `resources` to `SowMilestone`.

### Validation
- Added tests: `apps/api/tests/test_coaching_llm_contract.py`
  - Validator catches contract gaps for project story, ingestion doc links, and milestone resources.
  - Generation endpoint persists/returns LLM metadata and quality flags with retry behavior.
- Updated existing guardrail tests to include new strict SOW schema fields.

### Risks
- LLM integration currently depends on runtime API envs; missing/invalid keys fall back to scaffold output.
- Real-link validation blocks placeholder URLs by design; test payloads and fixtures must use production-style docs links.

### Needs
- Add deterministic schema-level nested models for `business_outcome.data_sources` and `resource_plan` items (currently dict-validated + custom validator checks).
- Add telemetry dashboard on generation quality flags over time (fallback rates, retry rates, invalid-link rates).

### Next
1. Add prompt versioning + experiment IDs in persisted generation metadata.
2. Add second-stage revision prompt path (LLM-guided fix-up) behind a feature flag for higher pass rates.
3. Add end-to-end API tests with mocked provider error/status branches.

## Checkpoint 2026-03-02 (Backend output template structure pass)

### Done
- Updated LLM generation contract/prompt in `apps/api/coaching.py` to enforce exemplar-like section flow while preserving personalization:
  - Added `REQUIRED_SECTION_FLOW` and injected explicit `top_level_order_required` + `section_flow` guidance into `required_contract`.
  - Strengthened hard rules to require exact section-order mirroring plus candidate-personalized narrative.
  - Updated system prompt to explicitly require exemplar order + personalized content.
- Added explicit structure validation and rejection behavior:
  - New `evaluate_sow_structure(...)` diagnostics helper returns expected/actual sequence, order validity, missing sections, and `structure_score`.
  - `validate_sow_payload(...)` now emits `SECTION_ORDER_INVALID` and `MISSING_SECTION` based on structural analysis.
  - `generate_sow_with_llm(...)` now rejects/retries LLM outputs that violate required structure contract before accepting output.
- Added structure diagnostics to quality scoring output consumed by generation responses:
  - `quality` now includes `structure_score`, `missing_sections`, and `section_order_valid`.
  - Findings now explicitly include `SECTION_ORDER_INVALID` when top-level flow is wrong.
- Added tests for structure completeness/order + diagnostics:
  - `apps/api/tests/test_coaching_llm_contract.py`
    - new coverage for missing sections + order mismatch in structure evaluator,
    - validator emits `SECTION_ORDER_INVALID` for reordered top-level blocks,
    - generate response now asserts structure diagnostics fields.

### Validation
- `python -m pytest tests/test_coaching_llm_contract.py tests/test_coaching_pass2.py tests/test_coaching_generation_guardrails.py -q` (from `apps/api`)

## Checkpoint Update (2026-03-02 - Sprint 2 Security Tasks A2/C1/E1/E2)

### Done
- **A2 security regression checks**
  - Added end-to-end regression coverage for coaching flow (`intake -> generate -> validate -> export`) in:
    - `apps/api/tests/test_security_sprint2.py::test_a2_security_regression_flow_intake_generate_validate_export`
- **C1 premium action security enforcement test coverage**
  - Enforced active-subscription checks on premium review/detail actions:
    - `GET /coaching/review/open-submissions`
    - `GET /coaching/review/submissions/{submission_id}/runs`
    - `GET /coaching/intake/submissions/{submission_id}`
  - Added coverage for subscription-denied behavior:
    - `apps/api/tests/test_security_sprint2.py::test_c1_premium_review_endpoints_require_active_subscription`
- **E1 LLM readiness security checks**
  - Added readiness endpoint:
    - `GET /coaching/health/llm-readiness`
  - Includes API-key presence and provider reachability signal (`/models` probe with safe timeout).
  - Added test coverage:
    - `apps/api/tests/test_security_sprint2.py::test_e1_llm_readiness_endpoint`
- **E2 URL/content safety hardening + tests**
  - Hardened URL safety in `apps/api/coaching.py`:
    - blocks unsafe schemes and private/loopback hosts
    - applies to job-link fetch path (`fetch_job_text`)
    - rejects unsupported content types for fetched job pages
  - Added regression test:
    - `apps/api/tests/test_security_sprint2.py::test_e2_fetch_job_text_blocks_unsafe_urls`

### Validation
- `python -m pytest -q tests/test_security_sprint2.py tests/test_llm_output_security.py tests/test_coaching_generation_guardrails.py` (from `apps/api`) — **9 passed**
- `python -m compileall .` (from `apps/api`) — **success**

### Risks
- Provider reachability probe currently checks transport/auth availability only; it does not validate model-level capability fit.
- Private-host blocking depends on DNS resolution behavior; highly custom DNS/network setups may require explicit allowlist controls.

### Needs from others
- Product/security decision on whether coach review endpoints should always require active subscription for `viewer` users in all environments.
- Ops decision on production allowlist policy for outbound job-link domains.

### Next
1. Add optional outbound domain allowlist config for job parsing (`ALLOWED_JOB_HOSTS`) with environment-based override.
2. Add readiness detail fields for model selection + last-successful provider check timestamp.
3. Add negative-path tests for provider probe failures (timeouts/401/5xx) in readiness endpoint coverage.

## Checkpoint Close (2026-03-02 - Sprint 2 Security Close Items)

### Done
- Added coach notes/status endpoint security coverage in `apps/api/tests/test_security_sprint2.py`:
  - `test_coach_review_status_update_forbids_viewer_role`
  - `test_coach_review_status_update_requires_active_subscription`
- Added regenerate quality-delta response leak regression in `apps/api/tests/test_llm_output_security.py`:
  - `test_regenerate_quality_delta_response_does_not_leak_prior_sensitive_payload`
  - Confirms `quality_delta` is returned while prior-run sensitive payload values/keys do not appear in API response.
- Added frontend link safety policy note + backend/frontend defense-in-depth section in:
  - `docs/coaching-project/HOSTED_APP_MEMBER_FLOW_THREAT_MODEL.md`

### Validation
- Targeted security regression suite run (from `apps/api`):
  - `python -m pytest -q tests/test_security_sprint2.py tests/test_llm_output_security.py`
  - Result: **9 passed**

### Sprint 2 Security Close Status
- This security close checkpoint is complete for requested items 1-4 (tests + docs + regression run).

## Checkpoint Update (2026-03-02 - Premium Output Quality Floor + Diagnostics)

### Done
- Strengthened SOW generation contract to demand richer milestone detail:
  - Added required milestone fields: `execution_plan`, `expected_deliverable`, `business_why`.
  - Updated LLM system/user contract prompt to explicitly require action detail, expected output quality, and business rationale per milestone.
- Enforced datasource quality floor in backend validator:
  - Requires at least one concrete public `business_outcome.data_sources[*].url`.
  - Requires at least one concrete `business_outcome.data_sources[*].ingestion_doc_url`.
  - Retains per-item link validation for each data source entry.
- Added quality floor auto-regeneration pass:
  - Introduced quality floor score of `80` in `/coaching/sow/generate`.
  - If output quality falls below floor after first revise/validation, performs one targeted auto-regeneration pass based on current deficiency findings.
- Added explicit quality diagnostics payload for frontend consumption:
  - `quality.quality_diagnostics` now includes `floor_score`, `below_floor`, `auto_regenerated`, `deficiency_codes`, `deficiency_count`, and `top_deficiencies`.
  - `quality_flags` now includes `auto_regenerated_for_quality_floor`.
- Surfaced diagnostics in coaching workbench UI quality card (floor score, auto-regenerated indicator, deficiency count, top deficiencies).

### Validation
- Backend compile check (from `apps/api`):
  - `.venv\\Scripts\\python -m py_compile main.py coaching.py models.py` � **success**
- Targeted backend tests attempted:
  - `.venv\\Scripts\\python -m pytest tests/test_coaching_generation_guardrails.py tests/test_coaching_llm_contract.py tests/test_coaching_pass2.py tests/test_coaching_sprint2_backend.py`
  - Blocked in environment due to missing dependency: `httpx` required by `starlette.testclient` during collection.
- Frontend build attempted (from `apps/web`):
  - `npm run build`
  - Blocked by existing workspace issue: `EISDIR ... src/app/page.tsx` (pre-existing structural/build config issue).

### Risks
- Quality auto-regeneration currently uses deterministic targeted revision logic (single pass) rather than second LLM revise call.
- Global datasource quality constraints are now strict and may fail older fixtures/payloads lacking explicit ingestion docs.

### Next
1. Add dedicated LLM deficiency-revision prompt path (feature-flagged) for higher fidelity remediation vs deterministic fallback.
2. Add typed nested models for data sources/resources to shift more validation into schema-level contracts.
3. Fix `apps/web` build path issue (`src/app/page.tsx` directory/file mismatch) so diagnostics UI changes can be CI-verified.
