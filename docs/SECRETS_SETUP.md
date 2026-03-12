# Secrets & Connector Setup

## Local development
1. Copy `.env.example` to `.env`
2. Fill in credentials locally
3. `.env` is gitignored by default
4. For this repo, keep `.env` at the repository root (`/workspace/gambill-coaching-project/.env`) so API startup can auto-load it.

## Recommended secret storage
- **GitHub Actions**: repository/environment secrets
- **Databricks**: secret scopes
- **Cloud runtime**: managed secret store (AWS/GCP/Azure)

## Required variables
- LLM provider:
  - `OPENAI_API_KEY` (primary)
  - `LLM_API_KEY` (fallback alias)
  - `OPENAI_BASE_URL` (optional override, defaults to `https://api.openai.com/v1`)
- LakeBase:
  - `LAKEBASE_HOST`
  - `LAKEBASE_PORT`
  - `LAKEBASE_DB`
  - `LAKEBASE_USER`
  - `LAKEBASE_PASSWORD`
  - `LAKEBASE_SSLMODE`
- Databricks:
  - `DATABRICKS_HOST`
  - `DATABRICKS_TOKEN`
  - `DATABRICKS_WAREHOUSE_ID` (for SQL/lineage queries)
  - `DATABRICKS_CATALOG` (optional default)
  - `DATABRICKS_SCHEMA` (optional default)

## Healthcheck
Run API and call:
`GET /health`

You should see connector-level status and any error messages for missing/bad credentials.
