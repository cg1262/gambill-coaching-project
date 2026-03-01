from models import CanvasAST


def test_canvas_ast_parses():
    payload = {
        "version": "1.0",
        "workspace_id": "ws-1",
        "tables": [
            {
                "id": "orders",
                "schema": "demo",
                "table": "orders",
                "columns": [
                    {"name": "id", "data_type": "string", "nullable": False, "is_primary_key": True}
                ],
                "position": {"x": 1, "y": 2},
                "source": "mock",
            }
        ],
        "relationships": [],
        "modified_table_ids": ["orders"],
    }
    ast = CanvasAST.model_validate(payload)
    assert ast.version == "1.0"
    assert ast.tables[0].table == "orders"
