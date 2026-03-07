from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from collections import Counter

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


def build_seeded_quality_trend_report() -> dict[str, Any]:
    bundle = build_seeded_artifact_bundle()
    artifacts = bundle.get("artifacts") or []

    deficiency_counter: Counter[str] = Counter()
    scenarios: list[dict[str, Any]] = []
    score_values: list[int] = []
    style_values: list[int] = []

    for artifact in artifacts:
        quality = artifact.get("quality") or {}
        score = int(quality.get("score") or 0)
        style = int(quality.get("style_alignment_score") or 0)
        major_deficiency_count = int(quality.get("major_deficiency_count") or 0)
        deficiency_codes = [str(code) for code in (quality.get("deficiency_codes") or []) if str(code).strip()]
        deficiency_counter.update(deficiency_codes)

        score_values.append(score)
        style_values.append(style)
        scenarios.append(
            {
                "scenario": artifact.get("scenario"),
                "score": score,
                "style_alignment_score": style,
                "major_deficiency_count": major_deficiency_count,
                "pass": major_deficiency_count == 0 and style >= 75 and score >= 80,
                "deficiency_codes": deficiency_codes,
            }
        )

    major_deficiency_total = sum(int(row.get("major_deficiency_count") or 0) for row in scenarios)
    passing = sum(1 for row in scenarios if bool(row.get("pass")))

    return {
        "report_version": "2026-03-sprint16",
        "source_bundle_version": bundle.get("bundle_version"),
        "scenario_count": len(scenarios),
        "pass_count": passing,
        "fail_count": len(scenarios) - passing,
        "quality_summary": {
            "average_score": round(sum(score_values) / len(score_values), 2) if score_values else 0,
            "average_style_alignment_score": round(sum(style_values) / len(style_values), 2) if style_values else 0,
            "major_deficiency_total": major_deficiency_total,
            "top_deficiency_codes": [
                {"code": code, "count": count}
                for code, count in deficiency_counter.most_common(5)
            ],
        },
        "production_gate": {
            "all_seeded_scenarios_pass": passing == len(scenarios),
            "zero_major_deficiencies": major_deficiency_total == 0,
            "minimum_style_alignment_score": 75,
            "minimum_quality_score": 80,
        },
        "scenarios": scenarios,
    }
