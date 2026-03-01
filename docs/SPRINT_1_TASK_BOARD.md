# Sprint 1 Task Board (P0 Focus)

Last Updated: 2026-02-24
Sprint Goal: Production-hardening baseline for security, ingestion reliability, and integration readiness.

## Epic 1 — Security Hardening (Owner: Security Agent)

### SEC-1: Upgrade connection secret crypto
- Priority: P0
- Description: Replace POC XOR scheme with production-grade encryption (AES-GCM/Fernet-compatible envelope)
- Acceptance Criteria:
  - New encrypt/decrypt helper implemented
  - Backward read support for legacy `enc:v1` payloads
  - New writes use `enc:v2` envelope
  - Unit tests for round-trip + malformed payload handling
- Dependencies: Backend agent
- Status: TODO

### SEC-2: Key rotation readiness
- Priority: P0
- Description: Add keyring-style config (active key + previous keys for decryption)
- Acceptance Criteria:
  - Config supports multiple keys
  - Decrypt attempts previous keys
  - Rotation runbook documented
- Dependencies: Backend agent
- Status: TODO

### SEC-3: Security regression tests
- Priority: P0
- Description: Add API tests for auth/rbac on standards/report endpoints
- Acceptance Criteria:
  - 200/403 paths validated for critical routes
  - CI test stage includes these tests
- Dependencies: Backend agent
- Status: TODO

---

## Epic 2 — Databricks Ingestion + Blast Radius Fidelity (Owner: Connectors Agent)

### CONN-1: Databricks schema sync resilience
- Priority: P0
- Description: Harden `/connections/sync/databricks-schema` against large schemas and edge types
- Acceptance Criteria:
  - Handles pagination/limits safely
  - Data type mapping covers common Databricks types
  - Clear errors for missing catalog/schema permissions
- Dependencies: Backend + Frontend
- Status: TODO

### CONN-2: Relationship inference baseline
- Priority: P1
- Description: Infer likely FK relationships from naming patterns (`*_id`) after import
- Acceptance Criteria:
  - Optional inference toggle
  - Inferred edges marked as inferred in metadata
- Dependencies: Frontend
- Status: TODO

### CONN-3: Connector diagnostics panel
- Priority: P1
- Description: Surface last sync status, object counts, and last error message in UI
- Acceptance Criteria:
  - Databricks panel shows last sync time + success/failure
  - Last error retained until next success
- Dependencies: Frontend
- Status: TODO

---

## Epic 3 — Governance Lifecycle Scale (Owner: Backend + Frontend)

### GOV-1: Audit filters + pagination API
- Priority: P0
- Description: Extend finding status audit endpoint with filter params and pagination
- Acceptance Criteria:
  - Filters: status, updated_by, date range
  - Pagination: page + page_size or cursor
  - UI consumes paginated results
- Dependencies: Frontend
- Status: TODO

### GOV-2: Finding status notes UX
- Priority: P1
- Description: Allow adding/editing notes when updating finding status
- Acceptance Criteria:
  - Note input in finding panel
  - Notes persist and appear in audit timeline
- Dependencies: Backend
- Status: TODO

---

## Epic 4 — CI/CD and PR Automation (Owner: Integrations Agent)

### CICD-1: Auto-post PR summary trigger
- Priority: P0
- Description: Add endpoint/flow for pipeline-triggered PR summary posting
- Acceptance Criteria:
  - Idempotency key prevents duplicate posts
  - Success/failure response includes provider diagnostics
- Dependencies: Backend
- Status: TODO

### CICD-2: Provider retry policy
- Priority: P1
- Description: Add controlled retry for transient provider failures (GitHub/GitLab)
- Acceptance Criteria:
  - Retries for 429/5xx with backoff
  - No retry for auth/permission errors
- Dependencies: Security
- Status: TODO

---

## Epic 5 — UX Reliability (Owner: Frontend Agent)

### UX-1: Workspace sync clarity
- Priority: P0
- Description: Make workspace id and connection source explicit in all connector actions
- Acceptance Criteria:
  - Workspace shown in panel
  - Action messages include workspace context
- Dependencies: None
- Status: DONE (baseline)

### UX-2: Import result details
- Priority: P0
- Description: Improve imported object list and add quick search/filter
- Acceptance Criteria:
  - Search within imported objects list
  - Counts + limited preview + export list
- Dependencies: None
- Status: TODO

---

## Orchestrator Integration Gates
Before sprint close, all of these must pass:
1. API compile checks pass
2. Web typecheck passes
3. Security tests pass
4. Databricks schema sync succeeds on test workspace
5. Findings lifecycle updates persist and audit timeline remains consistent
6. PR summary automation works for at least one provider in a test run

---

## Daily Reporting Format (for all agents)

```text
Done:
Validation:
Risks:
Needs from others:
Next:
```
