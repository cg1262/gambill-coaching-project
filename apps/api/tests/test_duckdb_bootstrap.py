import pytest

from db_lakebase import healthcheck, lakebase_connection
from config import settings


def test_duckdb_self_bootstrap_creates_db_and_tables(tmp_path):
    pytest.importorskip("duckdb")

    db_path = tmp_path / "lakebase" / "bootstrap.duckdb"

    settings.lakebase_backend = "duckdb"
    settings.lakebase_duckdb_path = str(db_path)

    ok, _ = healthcheck()
    assert ok is True
    assert db_path.exists()

    with lakebase_connection() as conn:
        tables = conn.execute("SHOW TABLES").fetchall()

    table_names = {row[0] for row in tables}
    expected = {
        "acronym_dictionary",
        "naming_rules",
        "canvas_projects",
        "canvas_versions",
        "validation_runs",
        "impact_runs",
    }
    assert expected.issubset(table_names)

    with lakebase_connection() as conn:
        acronym_count = conn.execute("SELECT COUNT(*) FROM acronym_dictionary").fetchone()[0]
        naming_count = conn.execute("SELECT COUNT(*) FROM naming_rules").fetchone()[0]

    assert acronym_count >= 3
    assert naming_count >= 2
