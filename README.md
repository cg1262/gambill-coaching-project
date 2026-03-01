# AI-Powered Data Modeling IDE

Phase 0 bootstrap for the DataTune March 2026 MVP.

## Objective
Build a proactive data modeling IDE that combines:
- Visual ERD authoring
- Databricks Unity Catalog sync + lineage
- Deterministic standards checks
- LLM-assisted probabilistic checks via RAG

## Phase 0 Deliverables (completed)
- Monorepo skeleton (web, api, contracts, mcp-server)
- Initial typed schema contract (TS + Python/Pydantic-aligned shape)
- FastAPI backend scaffold with strict separation of deterministic vs probabilistic endpoints
- Architecture + milestone docs for MVP execution

## Phase 1 (in progress)
- Env/secret-based connector configuration (`.env.example`, gitignored `.env`)
- LakeBase/Postgres connector scaffold + health checks
- Databricks Unity Catalog connector scaffold + health checks
- Deterministic validation/impact service wiring to connector layers
- React Flow web scaffold with live AST preview
- API contract/rule smoke tests (`apps/api/tests`)
- Demo AST seed packs (telecom/cyber/manufacturing/aviation)
- CI workflow for API compile/tests + web typecheck
- MCP tool wrapper scaffold for FastAPI endpoints

## Repository Layout
- `apps/web` — Next.js + React Flow frontend (scaffold placeholder)
- `apps/api` — FastAPI service
- `packages/contracts` — shared typed AST contracts
- `packages/mcp-server` — MCP wrappers for FastAPI tools (placeholder)
- `docs` — architecture, roadmap, implementation plans

## Immediate Next (Phase 1)
1. Implement strict AST validation end-to-end (TS + Pydantic v2)
2. Build deterministic validation engine (PK/naming/acronyms/catalog checks)
3. Build initial React Flow canvas and AST serializer
4. Add Qdrant retrieval + strict JSON violation output contract

## Running (API scaffold)
```bash
cd apps/api
python -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

## Notes
This phase intentionally prioritizes architecture integrity and typed contracts over UI polish.