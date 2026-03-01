# Agent Operating Model (ERD Program)

Last Updated: 2026-02-24

## Purpose
Define how multiple specialized agents collaborate to deliver the AI Data Modeling IDE quickly and safely.

---

## Agent Roles

### 1) Orchestrator (Master)
**Mission:** Own delivery flow, sequencing, integration, and release readiness.

**Responsibilities:**
- Prioritize roadmap (P0/P1/P2)
- Assign work to specialized agents
- Resolve cross-agent conflicts
- Enforce merge gates and Definition of Done
- Publish end-of-day integration summary

**Primary outputs:**
- Daily assignments
- Integration status
- Go/No-go release decision

---

### 2) Backend/Core Agent
**Mission:** Build stable API, data model, and platform services.

**Responsibilities:**
- API endpoints/contracts
- Models/service logic
- Persistence/schema updates
- Auth/session/RBAC core behavior
- Backend test coverage

**Primary outputs:**
- Endpoint changelog
- Passing compile/tests
- Migration/bootstrap notes

---

### 3) Frontend/UX Agent
**Mission:** Deliver clear, usable workflows and resilient UX states.

**Responsibilities:**
- UI implementation and state wiring
- Error/success/loading behaviors
- Data visualization and panel interactions
- Accessibility/readability polish

**Primary outputs:**
- UI behavior notes
- Typecheck pass
- Demo-ready interaction proof

---

### 4) Connectors/Integrations Agent
**Mission:** Deliver robust external connectivity and ingestion.

**Responsibilities:**
- Databricks/Power BI/GitHub/GitLab adapters
- Sync/ingestion endpoints
- Provider-specific payload handling
- Retry/failure diagnostics strategy

**Primary outputs:**
- Connector test matrix
- Sample payload docs
- Failure mode notes

---

### 5) Security/Hardening Agent
**Mission:** Reduce risk and raise production readiness.

**Responsibilities:**
- Secret handling + crypto hardening
- Audit trail integrity
- Security config guidance
- RBAC and hardening tests

**Primary outputs:**
- Security checklist status
- Risk findings + mitigations
- Required config/env changes

---

## Handoff Protocol (Required)
Every agent update must include:

1. **Done** (what changed)
2. **Validation** (tests/typecheck/compile)
3. **Risks** (known issues/assumptions)
4. **Needs from others** (explicit dependencies)
5. **Next** (immediate follow-up)

Template:

```text
Done:
Validation:
Risks:
Needs from others:
Next:
```

---

## Branching and Merge Policy
- Feature branches by lane:
  - `feat/backend-*`
  - `feat/frontend-*`
  - `feat/connectors-*`
  - `feat/security-*`
- Orchestrator owns integration merges into `master`.
- No direct ad-hoc changes to `master` without integration check.

---

## Daily Operating Cadence

### Start of Day
- Orchestrator publishes priorities and lane assignments.

### Midday
- Quick integration risk check and blocker resolution.

### End of Day
- Integration validation pass
- Update `docs/POC_DELIVERABLES_STATUS.md`
- Publish “done vs outstanding” summary

---

## Definition of Done (Per Task)
A task is done only when all are true:
- Implementation complete
- Tests/typecheck/compile pass
- Documentation updated
- No unresolved critical blockers
- Orchestrator integration acceptance

---

## Escalation Rules
Escalate to Orchestrator immediately when:
- API contract breaks another lane
- Security risk is discovered
- Integration tests fail repeatedly
- Required credentials/config are missing

---

## Specialist Agent Profiles
- Backend profile: `docs/agents/backend.md`
- Frontend profile: `docs/agents/frontend.md`
- Security profile: `docs/agents/security.md`

Use these as the base prompt/charter for specialist agents.

## Current Priority Alignment
1. Databricks schema ingestion + blast-radius fidelity
2. Security hardening (crypto upgrade + key rotation strategy)
3. CI/CD auto-post integration for PR summaries
4. Audit timeline scalability (filters/pagination)
