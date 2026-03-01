from __future__ import annotations
import os
import base64


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)


class Settings:
    # LakeBase backend (postgres | duckdb)
    lakebase_backend: str = _env("LAKEBASE_BACKEND", "postgres")

    # LakeBase / Postgres
    lakebase_host: str = _env("LAKEBASE_HOST", "")
    lakebase_port: int = int(_env("LAKEBASE_PORT", "5432"))
    lakebase_db: str = _env("LAKEBASE_DB", "")
    lakebase_user: str = _env("LAKEBASE_USER", "")
    lakebase_password: str = _env("LAKEBASE_PASSWORD", "")
    lakebase_sslmode: str = _env("LAKEBASE_SSLMODE", "require")

    # LakeBase / DuckDB
    lakebase_duckdb_path: str = _env("LAKEBASE_DUCKDB_PATH", "./lakebase.duckdb")

    # Databricks
    databricks_host: str = _env("DATABRICKS_HOST", "")
    databricks_token: str = _env("DATABRICKS_TOKEN", "")
    databricks_warehouse_id: str = _env("DATABRICKS_WAREHOUSE_ID", "")
    databricks_catalog: str = _env("DATABRICKS_CATALOG", "")
    databricks_schema: str = _env("DATABRICKS_SCHEMA", "")

    # Rule tables
    rules_acronym_table: str = _env("RULES_ACRONYM_TABLE", "governance.acronym_dictionary")
    rules_naming_table: str = _env("RULES_NAMING_TABLE", "governance.naming_rules")

    # Git AST versioning
    git_ast_repo_path: str = _env("GIT_AST_REPO_PATH", "")
    git_ast_branch: str = _env("GIT_AST_BRANCH", "")
    git_ast_remote: str = _env("GIT_AST_REMOTE", "origin")

    app_env: str = _env("APP_ENV", "dev")
    log_level: str = _env("LOG_LEVEL", "INFO")

    # Connection secret envelope (POC-level encryption scaffold)
    connection_secret_key: str = _env("CONNECTION_SECRET_KEY", "")

    def connection_secret_key_bytes(self) -> bytes:
        raw = (self.connection_secret_key or "").strip()
        if not raw:
            return b""
        try:
            return base64.urlsafe_b64decode(raw + "==")
        except Exception:
            return raw.encode("utf-8")


settings = Settings()
