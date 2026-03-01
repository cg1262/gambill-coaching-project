# Secrets & Connector Setup

## Local development
1. Copy `.env.example` to `.env`
2. Fill in credentials locally
3. `.env` is gitignored by default

## Recommended secret storage
- **GitHub Actions**: repository/environment secrets
- **Databricks**: secret scopes
- **Cloud runtime**: managed secret store (AWS/GCP/Azure)

## Required variables
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
