from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .sow_draft import build_sow_skeleton
from .sow_validation import build_quality_diagnostics, compute_sow_quality_score, validate_sow_payload


@dataclass(frozen=True)
class SeededScenario:
    key: str
    intake: dict[str, Any]
    parsed_jobs: list[dict[str, Any]]


def seeded_intake_scenarios() -> list[SeededScenario]:
    return [
        SeededScenario(
            key="retail_platform_modernization",
            intake={
                "applicant_name": "Avery",
                "preferences": {
                    "timeline_weeks": 6,
                    "resume_parse_summary": {
                        "role_level": "senior",
                        "years_experience_hint": 10,
                        "parse_confidence": 86,
                        "tools": ["python", "sql", "dbt", "airflow", "aws", "power bi"],
                        "domains": ["retail", "ecommerce"],
                        "project_experience_keywords": ["kpi", "forecasting", "data quality"],
                    },
                },
            },
            parsed_jobs=[{"signals": {"seniority": "senior", "skills": ["sql", "python"], "tools": ["dbt"], "domains": ["retail"]}}],
        ),
        SeededScenario(
            key="utilities_reliability_program",
            intake={
                "applicant_name": "Morgan",
                "preferences": {
                    "timeline_weeks": 7,
                    "resume_parse_summary": {
                        "role_level": "mid",
                        "years_experience_hint": 6,
                        "parse_confidence": 81,
                        "tools": ["python", "sql", "spark", "databricks", "azure"],
                        "domains": ["energy", "utilities"],
                        "project_experience_keywords": ["sla", "monitoring", "orchestration"],
                    },
                },
            },
            parsed_jobs=[{"signals": {"seniority": "mid", "skills": ["spark"], "tools": ["databricks"], "domains": ["energy"]}}],
        ),
        SeededScenario(
            key="healthcare_analytics_foundation",
            intake={
                "applicant_name": "Jordan",
                "preferences": {
                    "timeline_weeks": 10,
                    "resume_parse_summary": {
                        "role_level": "junior",
                        "years_experience_hint": 2,
                        "parse_confidence": 78,
                        "tools": ["python", "sql", "postgres"],
                        "domains": ["healthcare"],
                        "project_experience_keywords": ["dashboarding", "quality checks"],
                    },
                },
            },
            parsed_jobs=[{"signals": {"seniority": "mid", "skills": ["sql"], "tools": ["airflow"], "domains": ["healthcare"]}}],
        ),
    ]


def build_seeded_artifact_bundle() -> dict[str, Any]:
    scenarios = seeded_intake_scenarios()
    artifacts: list[dict[str, Any]] = []
    for case in scenarios:
        sow = build_sow_skeleton(intake=case.intake, parsed_jobs=case.parsed_jobs)
        findings = validate_sow_payload(sow)
        quality = compute_sow_quality_score(sow, findings)
        diagnostics = build_quality_diagnostics(quality, findings, workspace_id="ws-sprint14", submission_id=f"seed-{case.key}")
        artifacts.append(
            {
                "scenario": case.key,
                "applicant_name": case.intake.get("applicant_name"),
                "project_title": sow.get("project_title"),
                "quality": {
                    "score": quality.get("score"),
                    "style_alignment_score": quality.get("style_alignment_score"),
                    "major_deficiency_count": diagnostics.get("major_deficiency_count"),
                    "deficiency_codes": diagnostics.get("deficiency_codes"),
                },
                "sow": sow,
            }
        )

    return {
        "bundle_version": "2026-03-sprint14",
        "scenario_count": len(artifacts),
        "artifacts": artifacts,
    }
