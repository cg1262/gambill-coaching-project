import pytest

from config import settings
from db_lakebase import bootstrap_status


def test_bootstrap_status_duckdb(tmp_path):
    pytest.importorskip("duckdb")

    settings.lakebase_backend = "duckdb"
    settings.lakebase_duckdb_path = str(tmp_path / "status" / "lakebase.duckdb")

    status = bootstrap_status()

    assert status["backend"] == "duckdb"
    assert status["configured"] is True
    assert "duckdb_path" in status
    assert "acronym_dictionary" in status["tables"]
