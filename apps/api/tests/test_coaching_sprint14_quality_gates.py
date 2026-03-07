import json
from pathlib import Path

from coaching import build_sow_skeleton, build_quality_diagnostics, compute_sow_quality_score, validate_sow_payload

SNAPSHOT_FILE = Path(__file__).parent / "fixtures" / "sprint13_golden_sow_snapshots.json"


def _golden_intake(name: str, role_level: str, years: int, tools: list[str], domains: list[str], timeline_weeks: int = 6):
    return {
        "applicant_name": name,
        "preferences": {
            "timeline_weeks": timeline_weeks,
            "resume_parse_summary": {
                "role_level": role_level,
                "years_experience_hint": years,
                "parse_confidence": 82,
                "tools": tools,
                "domains": domains,
                "project_experience_keywords": ["medallion", "kpi", "data quality", "orchestration"],
            },
        },
    }


def _case_inputs():
    return {
        "globalmart": {
            "intake": _golden_intake("Avery", "senior", 9, ["python", "sql", "dbt", "airflow", "aws", "power bi"], ["retail", "ecommerce"]),
            "parsed_jobs": [{"signals": {"seniority": "senior", "skills": ["sql"], "tools": ["dbt"], "domains": ["retail"]}}],
        },
        "voltstream": {
            "intake": _golden_intake("Morgan", "mid", 6, ["python", "sql", "spark", "databricks", "azure"], ["energy", "telecom"]),
            "parsed_jobs": [{"signals": {"seniority": "senior", "skills": ["spark"], "tools": ["databricks"], "domains": ["energy"]}}],
        },
        "foundational": {
            "intake": _golden_intake("Jordan", "junior", 1, ["python", "sql"], ["healthcare"], timeline_weeks=10),
            "parsed_jobs": [{"signals": {"seniority": "mid", "skills": ["sql"], "tools": ["airflow"], "domains": ["healthcare"]}}],
        },
        "advanced_finops": {
            "intake": _golden_intake("Casey", "senior", 12, ["python", "sql", "dbt", "airflow", "aws", "spark", "databricks"], ["finance", "saas"], timeline_weeks=5),
            "parsed_jobs": [{"signals": {"seniority": "senior", "skills": ["spark", "sql"], "tools": ["databricks", "dbt"], "domains": ["finance"]}}],
        },
    }


def test_sprint14_required_golden_snapshot_gate_blocks_major_deficiency_drift():
    snapshots = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
    failures: list[str] = []

    for case_name, cfg in _case_inputs().items():
        sow = build_sow_skeleton(intake=cfg["intake"], parsed_jobs=cfg["parsed_jobs"])
        findings = validate_sow_payload(sow)
        quality = compute_sow_quality_score(sow, findings)
        diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-golden", submission_id=f"sub-{case_name}")

        expected = snapshots[case_name]
        if sow.get("project_title") != expected.get("project_title"):
            failures.append(f"{case_name}: project_title drift")
        if [m.get("name") for m in (sow.get("milestones") or [])] != expected.get("milestone_names"):
            failures.append(f"{case_name}: milestone_names drift")

        if int(diagnostics.get("major_deficiency_count") or 0) > 0:
            failures.append(
                f"{case_name}: major deficiencies detected {diagnostics.get('major_deficiency_codes') or []}"
            )

    assert not failures, "Golden quality gate failed:\n- " + "\n- ".join(failures)
