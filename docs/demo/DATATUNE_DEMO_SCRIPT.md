# DataTune Demo Script (MVP)

## Happy Path (7 minutes)
1. Open canvas with telecom sample AST.
2. Add/modify a column on `call_detail_record`.
3. Run deterministic validation:
   - show PK and naming checks.
4. Run deterministic blast radius:
   - show UC lineage-derived dependencies (100% confidence, green).
5. Run probabilistic checks:
   - show policy-guideline violations from RAG.
6. Show confidence gating:
   - only >=80 retained; color coded red/yellow/green.

## Failure Path (3 minutes)
1. Disable probabilistic service mock.
2. Show deterministic still works.
3. Show system degrades gracefully and preserves trusted checks.

## Closing
- Highlight separation of deterministic and probabilistic logic.
- Emphasize enterprise readiness for telecom/cyber/manufacturing/aviation complexity.
