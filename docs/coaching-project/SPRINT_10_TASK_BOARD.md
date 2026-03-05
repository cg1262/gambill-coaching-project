# SPRINT 10 TASK BOARD ? Coaching Output Quality v4

Sprint Goal: Ship anchor-aligned, portfolio-grade coaching outputs with hard quality gates that reject weak drafts.

## Scope
- Focus only on output quality v4 (no infra/platform scope).
- Style anchors:
  - GlobalMart Retail Intelligence Pipeline
  - VoltStream EV Grid Resilience

## Acceptance Criteria (Done = all true)
1. Generation prompt contract explicitly encodes anchor style/tone/structure and required section depth.
2. Validation rubric enforces:
   - realistic fictitious business story
   - concrete real public data source URLs
   - explicit ingestion instructions per data source
   - milestone-level acceptance checks
3. Hard quality gate prevents low-quality payload release:
   - below quality floor OR findings => auto-regenerate with deterministic scaffold
   - response includes gate flag metadata
4. Tests cover structure, depth, and style-alignment heuristics.
5. One fake intake and one full sample output generated after changes.

## Work Items
- [x] Add Sprint 10 board and v4 acceptance criteria
- [x] Tighten generation prompt + anchor contract
- [x] Expand validation rubric for ingestion instructions + acceptance checks + style alignment score
- [x] Enforce hard quality gate fallback/regeneration path in generation endpoint
- [x] Add Sprint 10 backend tests
- [x] Produce fake intake + sample full output
