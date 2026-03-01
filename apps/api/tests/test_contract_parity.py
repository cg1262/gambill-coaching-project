from models import CanvasAST


def _camel_ast_payload() -> dict:
    return {
        "version": "1.0",
        "workspaceId": "ws-camel",
        "tables": [
            {
                "id": "orders",
                "schema": "demo",
                "table": "orders",
                "columns": [
                    {
                        "name": "order_id",
                        "dataType": "string",
                        "nullable": False,
                        "isPrimaryKey": True,
                    }
                ],
                "position": {"x": 10, "y": 20},
                "source": "mock",
            }
        ],
        "relationships": [
            {
                "id": "rel-1",
                "fromTableId": "orders",
                "toTableId": "orders",
                "fromColumn": "order_id",
                "toColumn": "order_id",
                "relationshipType": "one_to_one",
            }
        ],
        "modifiedTableIds": ["orders"],
    }


def test_canvas_ast_accepts_camel_case_contract() -> None:
    ast = CanvasAST.model_validate(_camel_ast_payload())
    assert ast.workspace_id == "ws-camel"
    assert ast.tables[0].columns[0].data_type == "string"
    assert ast.relationships[0].from_table_id == "orders"


def test_canvas_ast_accepts_snake_case_contract() -> None:
    payload = {
        "version": "1.0",
        "workspace_id": "ws-snake",
        "tables": [
            {
                "id": "orders",
                "schema": "demo",
                "table": "orders",
                "columns": [
                    {
                        "name": "order_id",
                        "data_type": "string",
                        "nullable": False,
                        "is_primary_key": True,
                    }
                ],
                "position": {"x": 10, "y": 20},
                "source": "mock",
            }
        ],
        "relationships": [],
        "modified_table_ids": ["orders"],
    }
    ast = CanvasAST.model_validate(payload)
    assert ast.workspace_id == "ws-snake"
    assert ast.tables[0].columns[0].is_primary_key is True
