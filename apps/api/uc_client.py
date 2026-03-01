from __future__ import annotations

from typing import Any

from config import settings


def is_configured() -> bool:
    return all([
        settings.databricks_host,
        settings.databricks_token,
    ])


def workspace_client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient(host=settings.databricks_host, token=settings.databricks_token)


def healthcheck() -> tuple[bool, str]:
    if not is_configured():
        return False, "Databricks not configured"

    try:
        w = workspace_client()
        _ = w.current_user.me()
        return True, "ok"
    except Exception as e:
        return False, str(e)


def query_sql(sql: str) -> list[dict[str, Any]]:
    if not settings.databricks_warehouse_id:
        raise RuntimeError("DATABRICKS_WAREHOUSE_ID is required for SQL queries")

    from databricks.sql import connect
    with connect(
        server_hostname=settings.databricks_host.replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{settings.databricks_warehouse_id}",
        access_token=settings.databricks_token,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in rows]


def fetch_table_lineage(table_full_name: str, limit: int = 200) -> list[dict[str, Any]]:
    sql = (
        "SELECT * FROM system.access.table_lineage "
        f"WHERE source_table_full_name = '{table_full_name}' "
        f"OR target_table_full_name = '{table_full_name}' "
        f"LIMIT {limit}"
    )
    return query_sql(sql)


def query_sql_with_settings(sql: str, conn_settings: dict[str, Any]) -> list[dict[str, Any]]:
    host = str(conn_settings.get("host") or "").strip().replace("https://", "")
    token = str(conn_settings.get("token") or "").strip()
    http_path = str(conn_settings.get("http_path") or "").strip()
    warehouse_id = str(conn_settings.get("warehouse_id") or "").strip()

    if not host or not token:
        raise RuntimeError("Databricks host/token are required")

    if not http_path:
        if not warehouse_id:
            raise RuntimeError("Provide http_path or warehouse_id for Databricks SQL")
        http_path = f"/sql/1.0/warehouses/{warehouse_id}"

    from databricks.sql import connect
    with connect(
        server_hostname=host,
        http_path=http_path,
        access_token=token,
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
            cols = [d[0] for d in cursor.description] if cursor.description else []
            return [dict(zip(cols, row)) for row in rows]


def fetch_information_schema(conn_settings: dict[str, Any], limit_tables: int = 500, limit_columns: int = 5000) -> dict[str, list[dict[str, Any]]]:
    catalog = str(conn_settings.get("catalog") or "").strip()
    schema = str(conn_settings.get("schema") or "").strip()

    if not catalog:
        raise RuntimeError("Databricks catalog is required")

    schema_pred = ""
    if schema and schema not in {"*", "all", "ALL"}:
        schema_pred = f" AND lower(table_schema) = lower('{schema}') "

    table_sql = (
        f"SELECT table_catalog, table_schema, table_name, table_type "
        f"FROM {catalog}.information_schema.tables "
        f"WHERE 1=1 {schema_pred}"
        f"AND lower(table_schema) <> 'information_schema' "
        f"AND substr(table_name, 1, 2) <> '__' "
        f"ORDER BY table_schema, table_name LIMIT {int(limit_tables)}"
    )
    col_sql = (
        f"SELECT table_catalog, table_schema, table_name, column_name, data_type, is_nullable, ordinal_position "
        f"FROM {catalog}.information_schema.columns "
        f"WHERE 1=1 {schema_pred}"
        f"AND lower(table_schema) <> 'information_schema' "
        f"AND substr(table_name, 1, 2) <> '__' "
        f"ORDER BY table_schema, table_name, ordinal_position LIMIT {int(limit_columns)}"
    )

    tables = query_sql_with_settings(table_sql, conn_settings)
    columns = query_sql_with_settings(col_sql, conn_settings)
    return {"tables": tables, "columns": columns}


def fetch_schemas(conn_settings: dict[str, Any], limit: int = 500) -> list[str]:
    catalog = str(conn_settings.get("catalog") or "").strip()
    if not catalog:
        raise RuntimeError("Databricks catalog is required")

    sql = (
        f"SELECT DISTINCT table_schema "
        f"FROM {catalog}.information_schema.tables "
        f"WHERE lower(table_schema) <> 'information_schema' "
        f"ORDER BY table_schema LIMIT {int(limit)}"
    )
    rows = query_sql_with_settings(sql, conn_settings)
    out: list[str] = []
    for r in rows:
        s = str(r.get("table_schema") or "").strip()
        if s:
            out.append(s)
    return out
