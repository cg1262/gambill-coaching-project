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
