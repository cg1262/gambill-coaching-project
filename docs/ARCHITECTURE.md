# Architecture (MVP)

## Core Principle
A strict **two-pass validation pipeline**:
1. Deterministic pass (DB/catalog/rules)
2. Probabilistic pass (LLM + RAG)

Never mix both categories in a single function.

## Components
- **Frontend (Next.js + React Flow)**
  - Visual canvas for entities/relationships
  - Emits strict JSON AST
- **API (FastAPI + Pydantic v2)**
  - Validates AST
  - Routes to deterministic or probabilistic engines
- **LakeBase (Postgres)**
  - Session/canvas state
  - Deterministic rule tables (acronyms, naming dictionaries)
- **Databricks Unity Catalog**
  - Metadata sync
  - Deterministic lineage source (`system.access.table_lineage`, `column_lineage`)
- **Qdrant**
  - Embeddings of governance rules/docs
- **LLM via LangChain + MCP tools**
  - Probabilistic schema checks
  - Shadow dependency inference with confidence scores

## Validation Flow
1. Canvas AST submitted to API.
2. API runs deterministic validator:
   - PK checks
   - naming conventions
   - acronym dictionary checks
   - UC metadata consistency
3. API runs probabilistic validator (optional/second pass):
   - query Qdrant for relevant standards
   - invoke LLM with strict JSON output schema
4. Merge findings into unified response.

## Blast Radius Flow
- Deterministic lineage dependencies => confidence 100 (Green)
- LLM inferred dependencies => confidence 0-100
- Backend drops `< 80`
- UI coloring:
  - Red: 80-84
  - Yellow: 85-94
  - Green: 95-100

## Security + Reliability
- Strict response schemas for LLM outputs
- Confidence gating enforced server-side
- No direct LLM writes to persistent model state
- Audit log per validation run
