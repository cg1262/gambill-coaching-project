from models import CanvasAST
from services import run_deterministic_validation


def test_missing_pk_violation():
    ast = CanvasAST.model_validate({
        "version": "1.0",
        "workspace_id": "ws-2",
        "tables": [
            {
                "id": "t1",
                "schema": "demo",
                "table": "Orders",
                "columns": [{"name": "name", "data_type": "string", "nullable": True}],
                "position": {"x": 0, "y": 0},
                "source": "mock",
            }
        ],
        "relationships": [],
    })
    result = run_deterministic_validation(ast)
    codes = {v.code for v in result.violations}
    assert "MISSING_PRIMARY_KEY" in codes
    assert "TABLE_NAMING_CONVENTION" in codes


def test_pk_suffix_rule_violation():
    ast = CanvasAST.model_validate({
        "version": "1.0",
        "workspace_id": "ws-3",
        "tables": [
            {
                "id": "t2",
                "schema": "demo",
                "table": "orders",
                "columns": [{"name": "pk", "data_type": "string", "nullable": False, "is_primary_key": True}],
                "position": {"x": 0, "y": 0},
                "source": "mock",
            }
        ],
        "relationships": [],
    })
    result = run_deterministic_validation(ast)
    codes = {v.code for v in result.violations}
    assert "PRIMARY_KEY_SUFFIX" in codes
