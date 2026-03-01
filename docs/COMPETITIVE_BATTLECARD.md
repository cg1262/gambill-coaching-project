# Competitive Battlecard — AI Data Modeling IDE vs SQLDBM

Last Updated: 2026-02-27
Audience: Founder, product, technical pre-sales

## 1) Positioning (Use This)
**Category:** Governance-native data model change assurance platform (Databricks-first)

**One-liner:**
We help teams make schema changes safe, explainable, and auditable before production by combining ERD, standards validation, and blast-radius analysis in one workflow.

**Do NOT position as:**
- “another ERD tool”
- “SQLDBM clone”

---

## 2) Why We Win (Wedge)
1. **Safe-change workflow** end-to-end:
   - import real schema
   - run standards/regulatory checks
   - evaluate blast radius
   - publish auditable artifacts into PR/review flow
2. **Governance traceability** (finding -> source reference -> lifecycle status -> audit trail)
3. **Developer-operable outputs** (AST/findings/PR summaries)

---

## 3) Head-to-Head Snapshot

### SQLDBM Strengths
- Broad and mature modeling coverage
- Strong forward/reverse engineering footprint
- DataOps and observability modules documented
- Broad integration footprint

### Our Strengths
- Governance-native workflow tightly coupled to model changes
- Findings lifecycle + audit behavior integrated in product flow
- Practical PR artifact and summary automation hooks
- Databricks-first schema import and blast-radius foundation

### Our Current Gaps
- Platform breadth parity (not the goal right now)
- Production-grade security hardening completion
- Deeper dependency ingestion breadth for blast radius fidelity

---

## 4) Objection Handling

### Objection: “SQLDBM already does modeling + integrations.”
**Response:**
Agreed. We are not trying to out-breadth their modeling footprint. We focus on making model changes governable and reviewable with standards validation + blast radius + auditable PR artifacts in one flow.

### Objection: “This looks early for enterprise.”
**Response:**
Correct—we are in focused wedge execution mode. Security hardening and operational reliability tasks are prioritized in Sprint 1 with explicit acceptance gates.

### Objection: “Why not stay with current stack + process docs?”
**Response:**
Current stack often fragments design, governance, impact analysis, and change review. We reduce handoff friction and improve decision confidence before merge.

---

## 5) Demo Talk Track (10–12 min)
1. Import Databricks schema into canvas.
2. Run standards/regulatory checks; show findings and source refs.
3. Mark lifecycle status; show audit timeline.
4. Run blast radius and explain impacted downstream objects.
5. Export and post PR artifacts (summary + AST/findings).

**Close question:**
“Would this reduce your review cycle time and increase confidence on model changes?”

---

## 6) Qualification Signals (Continue/Stop)
Continue investing if, in 30 days:
- 3–5 target users complete workflow
- >=2 ask to pilot
- clear evidence of reduced review effort/risk

Pivot/stop if:
- users view this as redundant ERD tooling
- no measurable review/risk improvement in pilot usage

---

## 7) Strategic Guardrails
- Stay Databricks-first until wedge is proven.
- Do not pursue broad feature parity with incumbents.
- Prioritize reliability and trust over net-new surface area.
- Tie every roadmap item to “safe change” outcome.
