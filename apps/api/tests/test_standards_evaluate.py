from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from auth import Session, get_current_session


def test_standards_evaluate_flags_pii_column():
    app.dependency_overrides[get_current_session] = lambda: Session(
        username="tester", role="admin", expires_at=datetime.now(timezone.utc)
    )
    client = TestClient(app)

    payload = {
        "version": "1.0",
        "workspace_id": "ws-test",
        "tables": [
            {
                "id": "users",
                "schema": "demo",
                "table": "users",
                "description": "",
                "columns": [
                    {"name": "user_id", "data_type": "string", "nullable": False, "is_primary_key": True},
                    {"name": "email_address", "data_type": "string", "nullable": True},
                ],
                "position": {"x": 0, "y": 0},
                "source": "mock",
            }
        ],
        "relationships": [],
        "modified_table_ids": ["users"],
    }

    res = client.post("/standards/evaluate", json=payload)
    assert res.status_code == 200
    findings = (res.json() or {}).get("findings", [])
    assert any("PII" in f.get("finding", "") for f in findings)

    app.dependency_overrides = {}


def test_standards_evaluate_flags_generic_column_name():
    app.dependency_overrides[get_current_session] = lambda: Session(
        username="tester", role="admin", expires_at=datetime.now(timezone.utc)
    )
    client = TestClient(app)

    payload = {
        "version": "1.0",
        "workspace_id": "ws-test-generic",
        "tables": [
            {
                "id": "metrics",
                "schema": "demo",
                "table": "metrics",
                "description": "Has table description",
                "columns": [
                    {"name": "metric_id", "data_type": "string", "nullable": False, "is_primary_key": True},
                    {"name": "value", "data_type": "string", "nullable": True},
                ],
                "position": {"x": 0, "y": 0},
                "source": "mock",
            }
        ],
        "relationships": [],
        "modified_table_ids": ["metrics"],
    }

    res = client.post("/standards/evaluate", json=payload)
    assert res.status_code == 200
    findings = (res.json() or {}).get("findings", [])
    assert any("forbidden" in f.get("finding", "").lower() for f in findings)

    app.dependency_overrides = {}
