# Project Requirements (v1)

Owner: Chris Gambill  
Date: 2026-02-23

## Product Outcomes

1. Provide an AI-powered data modeling IDE with a visual ERD editor.
2. Show blast radius for model changes across data platform assets.
3. Validate designs against configurable standards, governance, and regulatory expectations.
4. Support enterprise-friendly versioning, auditability, and controlled collaboration.
5. Deliver a polished, visually engaging UX aligned to brand palette.

---

## Functional Requirements

### R1. Visual ERD authoring
- Users can create/edit table objects and relationships on a canvas.
- Users can edit schema/table names and column attributes.
- Users can export/import AST JSON.

### R2. Deterministic validation
- Validate PK, naming conventions, and acronym usage.
- Rule logic should be driven by configurable rule sources (not hardcoded only).
- Return explainable findings with code/severity/object mapping.

### R3. Probabilistic validation
- Use retrieval + LLM for policy interpretation and soft-dependency detection.
- Enforce strict structured output contract.
- Apply confidence gating and source labels.

### R4. Blast radius analysis (primary business outcome)
- Calculate impact breadth for changed model objects.
- Include deterministic and probabilistic impact layers.
- Target coverage by layers:
  - Core: tables/views
  - Next: pipelines/jobs, notebooks/code refs
  - Advanced: BI/report impact (Power BI datasets/reports)

### R5. Standards/governance management
- Provide templates for common standards/rules.
- Allow users to configure template values/options.
- Allow custom standards/governance/regulatory document upload.
- Parse, index, and evaluate uploaded content in checks.

### R6. Versioning and auditability
- Persist model versions and run history.
- Stamp actor identity on validation/impact/versioning actions.
- Support git-backed AST version control (repo/branch/remote per workspace).

### R7. Security and access control
- Require authentication for protected actions.
- Role-based access for config/push and other sensitive operations.
- Store credentials securely (hashed), no plaintext auth.

### R8. UX and aesthetics
- Apply brand color palette consistently.
- Use color hierarchy to improve readability and engagement.
- Present status/risk states with clear visual semantics.
- Improve visual polish (depth, contrast, accents, typography rhythm).

---

## Non-Functional Requirements

- Reliability for live demos (happy path + fallback path).
- Explainability (show deterministic vs probabilistic origins).
- Extensibility for new connectors and rule packs.
- Performance acceptable for interactive editing and validation cycles.

---

## Requirement Matrix (Current Status)

- R1 Visual ERD authoring: PARTIAL
  - Canvas/object/relationship editing implemented.
  - Needs additional UX polish and advanced controls.

- R2 Deterministic validation: PARTIAL
  - PK/naming/acronym checks implemented.
  - Rule-table driven behavior started.
  - Needs broader rule coverage.

- R3 Probabilistic validation: IN PROGRESS
  - Endpoint scaffold and confidence patterns present.
  - Full RAG + strict parser pipeline still needed.

- R4 Blast radius analysis: PARTIAL
  - Deterministic/probabilistic impact endpoints in place.
  - UC lineage integration path scaffolded.
  - Pipeline/notebook/Power BI breadth still to implement.

- R5 Standards/governance management: IN PROGRESS
  - Naming/acronym rule tables seeded.
  - Full template system + document upload/parse/index still pending.

- R6 Versioning and auditability: PARTIAL
  - AST versions/runs persisted, actor stamping added.
  - Git push flow added with workspace config.
  - Needs richer run history UX + compliance-grade audit views.

- R7 Security and access control: PARTIAL
  - Login + bearer token + role checks added.
  - Password hashing added.
  - Needs stronger production session strategy + user lifecycle ops.

- R8 UX and aesthetics: IN PROGRESS
  - Brand tokens and gradients exist.
  - Needs stronger visual hierarchy, richer color usage, and modernized styling system.

---

## Suggested Next Iteration Priorities

1. Blast Radius Expansion
   - Add dependency node types: pipeline, notebook, report.
   - Integrate available lineage sources and map into unified graph.
   - Implement confidence/source overlays.

2. Standards Engine Productization
   - Build rule template model + editor.
   - Add document upload + parsing + retrieval indexing.
   - Surface policy traceability in findings.

3. Security Hardening
   - Move from in-memory sessions to persistent/JWT approach.
   - Add user management (create/disable/reset/role change).
   - Add logout/revocation and tighter permission boundaries.

4. Frontend Aesthetic Pass
   - Define theme scale (primary/secondary/surface/elevation/interactive states).
   - Add section color accents and improved spacing/typography.
   - Introduce status chips, cards, and subtle motion for interaction feedback.

5. Demo Hardening
   - One-click scripted demo states.
   - Resilient fallback behavior when external connectors are unavailable.
