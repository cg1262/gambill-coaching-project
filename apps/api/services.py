from __future__ import annotations

import re
from uuid import uuid4

from models import CanvasAST, ValidationResult, Violation, ImpactResult, Dependency
from db_lakebase import (
    fetch_acronym_dictionary,
    fetch_dependency_mappings,
    fetch_naming_rules,
    save_canvas_version,
    save_impact_run,
    save_validation_run,
)
from uc_client import fetch_table_lineage
from probabilistic import gate_findings, confidence_to_color


# ------------------------------
# Deterministic services
# ------------------------------
def run_deterministic_validation(ast: CanvasAST, actor_user: str = "system") -> ValidationResult:
    violations: list[Violation] = []

    acronym_rows = fetch_acronym_dictionary(limit=2000)
    known_acronyms = {str(r.get("acronym", "")).lower() for r in acronym_rows if r.get("acronym")}

    naming_rows = fetch_naming_rules(limit=500)
    naming_rules = {str(r.get("rule_key", "")): str(r.get("rule_value", "")) for r in naming_rows if r.get("rule_key")}
    table_case_rule = naming_rules.get("table_case", "snake_lower")
    column_case_rule = naming_rules.get("column_case", "snake_lower")
    pk_suffix_rule = naming_rules.get("pk_suffix", "_id")

    snake_lower_re = re.compile(r"^[a-z][a-z0-9_]*$")

    for table in ast.tables:
        has_pk = any(c.is_primary_key for c in table.columns)
        if not has_pk:
            violations.append(
                Violation(
                    code="MISSING_PRIMARY_KEY",
                    severity="HIGH",
                    message=f"{table.schema}.{table.table} has no primary key.",
                    table_id=table.id,
                    source="deterministic",
                )
            )

        if table_case_rule == "snake_lower" and not snake_lower_re.match(table.table):
            violations.append(
                Violation(
                    code="TABLE_NAMING_CONVENTION",
                    severity="MED",
                    message=f"{table.table} should be snake_case lowercase.",
                    table_id=table.id,
                    source="deterministic",
                )
            )

        for col in table.columns:
            if column_case_rule == "snake_lower" and not snake_lower_re.match(col.name):
                violations.append(
                    Violation(
                        code="COLUMN_NAMING_CONVENTION",
                        severity="LOW",
                        message=f"Column {col.name} should be snake_case lowercase.",
                        table_id=table.id,
                        column_name=col.name,
                        source="deterministic",
                    )
                )

            if col.is_primary_key and pk_suffix_rule and not col.name.endswith(pk_suffix_rule):
                violations.append(
                    Violation(
                        code="PRIMARY_KEY_SUFFIX",
                        severity="LOW",
                        message=f"Primary key column {col.name} should end with '{pk_suffix_rule}'.",
                        table_id=table.id,
                        column_name=col.name,
                        source="deterministic",
                    )
                )

            parts = col.name.split("_")
            for p in parts:
                if len(p) >= 2 and p.isupper() and p.lower() not in known_acronyms:
                    violations.append(
                        Violation(
                            code="UNKNOWN_ACRONYM",
                            severity="LOW",
                            message=f"Column {col.name} includes acronym '{p}' not found in dictionary.",
                            table_id=table.id,
                            column_name=col.name,
                            source="deterministic",
                        )
                    )

    result = ValidationResult(violations=violations)

    try:
        project_id = ast.workspace_id
        save_canvas_version(str(uuid4()), project_id, actor_user, ast.model_dump(mode="json"))
        save_validation_run(
            run_id=str(uuid4()),
            project_id=project_id,
            actor_user=actor_user,
            pass_type="deterministic",
            violations=[v.model_dump(mode="json") for v in result.violations],
        )
    except Exception:
        pass

    return result


def run_deterministic_impact(ast: CanvasAST, actor_user: str = "system") -> ImpactResult:
    dependencies: list[Dependency] = []
    table_index = {t.id: t for t in ast.tables}
    modified_full_names: list[str] = []

    for table_id in ast.modified_table_ids:
        table = table_index.get(table_id)
        if not table:
            continue

        full_name = f"{table.catalog + '.' if table.catalog else ''}{table.schema}.{table.table}"
        modified_full_names.append(full_name)
        rows = fetch_table_lineage(full_name, limit=200)

        for row in rows:
            obj = row.get("target_table_full_name") or row.get("source_table_full_name") or "unknown_object"
            dependencies.append(
                Dependency(
                    object_name=str(obj),
                    dependency_type="table",
                    source="deterministic",
                    confidence=100.0,
                    color="green",
                )
            )

    for row in fetch_dependency_mappings(ast.workspace_id, modified_full_names):
        dep_type = str(row.get("dependency_type") or "pipeline")
        if dep_type not in {"table", "view", "pipeline", "code_ref"}:
            dep_type = "pipeline"
        conf = float(row.get("confidence") or 85.0)
        dependencies.append(
            Dependency(
                object_name=str(row.get("target_object") or "unknown_object"),
                dependency_type=dep_type,
                source="deterministic",
                confidence=conf,
                color=confidence_to_color(conf),
            )
        )

    dedup: dict[tuple[str, str], Dependency] = {}
    for d in dependencies:
        key = (d.object_name, d.dependency_type)
        prev = dedup.get(key)
        if (prev is None) or (d.confidence > prev.confidence):
            dedup[key] = d

    result = ImpactResult(dependencies=list(dedup.values()))

    try:
        save_impact_run(
            run_id=str(uuid4()),
            project_id=ast.workspace_id,
            actor_user=actor_user,
            pass_type="deterministic",
            dependencies=[d.model_dump(mode="json") for d in result.dependencies],
        )
    except Exception:
        pass

    return result


# ------------------------------
# Probabilistic services
# ------------------------------
def run_probabilistic_validation(ast: CanvasAST, actor_user: str = "system") -> ValidationResult:
    # Placeholder for Qdrant retrieval + LLM structured JSON output
    result = ValidationResult(violations=[])
    try:
        save_validation_run(
            run_id=str(uuid4()),
            project_id=ast.workspace_id,
            actor_user=actor_user,
            pass_type="probabilistic",
            violations=[v.model_dump(mode="json") for v in result.violations],
        )
    except Exception:
        pass
    return result


def run_probabilistic_impact(ast: CanvasAST, actor_user: str = "system") -> ImpactResult:
    # Placeholder: in Phase 2 this list is produced by LLM+RAG.
    raw = [
        {
            "object_name": "legacy_proc_order_rollup",
            "dependency_type": "code_ref",
            "confidence": 83.0,
            "rationale": "Dynamic SQL references the orders aggregate table alias.",
        },
        {
            "object_name": "low_confidence_shadow_ref",
            "dependency_type": "code_ref",
            "confidence": 55.0,
            "rationale": "Weak pattern match only.",
        },
    ]

    approved = gate_findings(raw, min_confidence=80)
    inferred: list[Dependency] = [
        Dependency(
            object_name=f.object_name,
            dependency_type=f.dependency_type,
            source="probabilistic",
            confidence=f.confidence,
            color=confidence_to_color(f.confidence),
        )
        for f in approved
    ]

    result = ImpactResult(dependencies=inferred)
    try:
        save_impact_run(
            run_id=str(uuid4()),
            project_id=ast.workspace_id,
            actor_user=actor_user,
            pass_type="probabilistic",
            dependencies=[d.model_dump(mode="json") for d in result.dependencies],
        )
    except Exception:
        pass

    return result
