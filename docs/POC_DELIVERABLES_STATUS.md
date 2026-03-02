# POC Deliverables Status

Last Updated: 2026-03-01
Owner: ERD Program Team

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
