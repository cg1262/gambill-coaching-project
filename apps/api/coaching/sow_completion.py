from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import TAG_TOPIC_MAP, CHARTER_REQUIRED_SECTION_FLOW
from .sow_draft import build_sow_skeleton
from .sow_validation import validate_sow_payload
from .sow_security import utc_now_iso


def _load_resource_library(resource_file: str | Path) -> dict[str, Any]:
    return json.loads(Path(resource_file).read_text(encoding="utf-8"))


def _resource_topics(resource: dict[str, Any]) -> set[str]:
    return {str(t).strip().lower() for t in (resource.get("topics") or []) if str(t).strip()}


def auto_revise_sow_once(sow: dict[str, Any], findings: list[dict[str, str]]) -> dict[str, Any]:
    _ = findings
    out = dict(sow)
    if not isinstance(out.get("solution_architecture"), dict):
        out["solution_architecture"] = {}
    if not isinstance((out.get("solution_architecture") or {}).get("medallion_plan"), dict):
        out["solution_architecture"]["medallion_plan"] = {}
    med = out["solution_architecture"]["medallion_plan"]
    med.setdefault("bronze", "Raw ingestion and CDC capture.")
    med.setdefault("silver", "Conformance, quality checks, and SCD handling.")
    med.setdefault("gold", "KPI marts and executive analytics consumption layer.")

    if not isinstance(out.get("project_story"), dict):
        out["project_story"] = {}
    out["project_story"].setdefault("executive_summary", "Current state reporting is delayed by fragmented extracts and manual reconciliation, while the future state is a governed KPI delivery cadence with transparent SLA tracking and stakeholder confidence in decision-grade metrics.")
    out["project_story"].setdefault("challenge", "Source systems are inconsistent and require governance controls, ingestion standards, and ownership alignment before executive reporting can be trusted for weekly operating reviews.")
    out["project_story"].setdefault("approach", "Implement medallion layers with automated data quality checks, lineage-aware modeling, and repeatable release evidence so each KPI can be traced from source ingestion through business consumption.")
    out["project_story"].setdefault("impact_story", "Expected impact includes reducing pipeline SLA misses, improving dashboard adoption, and providing measurable cost and revenue signal clarity for faster leadership decisions.")

    if not isinstance(out.get("business_outcome"), dict):
        out["business_outcome"] = {}
    if not isinstance((out.get("business_outcome") or {}).get("data_sources"), list):
        out["business_outcome"]["data_sources"] = []
    if not (out["business_outcome"].get("data_sources") or []):
        out["business_outcome"]["data_sources"] = [
            {
                "name": "US Bureau of Labor Statistics",
                "url": "https://www.bls.gov/data/",
                "ingestion_doc_url": "https://www.bls.gov/developers/home.htm",
                "selection_rationale": "Public API-backed labor data supports robust ingestion and KPI storytelling without private data dependencies.",
                "ingestion_instructions": "Use the BLS API v2 endpoint in daily batch mode, land raw JSON to bronze, and persist request metadata for replay.",
            }
        ]

    for ds in (out.get("business_outcome") or {}).get("data_sources") or []:
        if isinstance(ds, dict) and not str(ds.get("selection_rationale") or "").strip():
            ds["selection_rationale"] = "Selected as a public, documentation-backed source aligned to the target business outcome and delivery timeline."

    if not isinstance(out.get("milestones"), list) or not out.get("milestones"):
        out["milestones"] = [
            {"name": "Planning", "duration_weeks": 1, "deliverables": ["scope"], "milestone_tags": ["discovery"], "resources": [{"title": "Discovery checklist", "url": "https://www.atlassian.com/software/jira/guides"}]},
            {"name": "Build", "duration_weeks": 2, "deliverables": ["pipelines"], "milestone_tags": ["bronze", "silver"], "resources": [{"title": "Airflow docs", "url": "https://airflow.apache.org/docs/"}]},
            {"name": "Report", "duration_weeks": 1, "deliverables": ["dashboard"], "milestone_tags": ["gold", "roi"], "resources": [{"title": "Looker modeling", "url": "https://cloud.google.com/looker/docs"}]},
        ]
    normalized_milestones: list[dict[str, Any]] = []
    for ms in (out.get("milestones") or []):
        if not isinstance(ms, dict):
            continue
        if not str(ms.get("execution_plan") or "").strip():
            ms["execution_plan"] = "Break work into implementation tasks, owners, and checkpoints with explicit acceptance criteria."
        if not str(ms.get("expected_deliverable") or "").strip():
            ms["expected_deliverable"] = "Deliverable is complete, validated, and demo-ready with reproducible evidence."
        if not str(ms.get("business_why") or "").strip():
            ms["business_why"] = "Milestone output should improve delivery speed, trust, or measurable business value."
        if not (ms.get("resources") or []):
            ms["resources"] = [{"title": "Project delivery best practices", "url": "https://www.pmi.org/learning/library"}]
        if not (ms.get("acceptance_checks") or []):
            ms["acceptance_checks"] = [
                "Demo evidence recorded and linked in README",
                "Coach validates milestone quality against completion criteria",
            ]
        normalized_milestones.append(ms)
    out["milestones"] = normalized_milestones

    out.setdefault("roi_dashboard_requirements", {})
    out["roi_dashboard_requirements"].setdefault("required_dimensions", ["time", "business_unit"])
    out["roi_dashboard_requirements"].setdefault("required_measures", ["cost_savings"])

    out.setdefault("project_charter", {})
    out["project_charter"].setdefault("section_order", list(CHARTER_REQUIRED_SECTION_FLOW))
    sections = out["project_charter"].setdefault("sections", {})
    for required_section in CHARTER_REQUIRED_SECTION_FLOW:
        sections.setdefault(required_section, {})

    out.setdefault("resource_plan", {})
    if not (out["resource_plan"].get("required") or []):
        out["resource_plan"]["required"] = [{"title": "Choose an open source license", "url": "https://choosealicense.com/"}]
    out["resource_plan"].setdefault("recommended", [])
    out["resource_plan"].setdefault("optional", [])
    out["resource_plan"].setdefault(
        "affiliate_disclosure",
        "Some recommended resources may include affiliate links. Recommendations are selected for project relevance first.",
    )
    out["resource_plan"].setdefault(
        "trust_language",
        "Resource recommendations are optional and do not change coaching feedback or project scoring.",
    )

    out.setdefault("mentoring_cta", {})
    out["mentoring_cta"].setdefault(
        "trust_language",
        "Mentoring recommendations are guidance-only and should align with the candidate's goals and budget.",
    )

    return out


def match_resources_for_sow(sow: dict[str, Any], resource_file: str | Path) -> dict[str, Any]:
    library = _load_resource_library(resource_file)
    resources = library.get("resources") or []

    milestone_topics: set[str] = set()
    for milestone in (sow.get("milestones") or []):
        for tag in (milestone.get("milestone_tags") or []):
            mapped = TAG_TOPIC_MAP.get(str(tag).strip().lower()) or []
            milestone_topics.update(mapped)
        name = str(milestone.get("name") or "").lower()
        if "bronze" in name:
            milestone_topics.update(TAG_TOPIC_MAP["bronze"])
        if "silver" in name:
            milestone_topics.update(TAG_TOPIC_MAP["silver"])
        if "gold" in name:
            milestone_topics.update(TAG_TOPIC_MAP["gold"])

    target_tools = {str(x).strip().lower() for x in ((sow.get("solution_architecture") or {}).get("primary_tools") or [])}
    target_skills = {str(x).strip().lower() for x in ((sow.get("solution_architecture") or {}).get("target_skills") or [])}

    scored: list[tuple[int, dict[str, Any]]] = []
    for r in resources:
        topics = _resource_topics(r)
        score = len(topics.intersection(milestone_topics))
        score += len(topics.intersection(target_tools))
        score += len(topics.intersection(target_skills))
        if score > 0:
            scored.append((score, r))

    scored.sort(key=lambda x: (-x[0], x[1].get("id", "")))
    top = [x[1] for x in scored[:8]]

    required = top[:3]
    recommended = top[3:6]
    optional = top[6:8]

    return {
        "required": required,
        "recommended": recommended,
        "optional": optional,
        "match_meta": {
            "milestone_topics": sorted(milestone_topics),
            "total_candidates": len(scored),
        },
        "mentoring": library.get("mentoring") or {},
    }


def compose_demo_project_package(sample_intake: dict[str, Any], resource_file: str | Path) -> dict[str, Any]:
    parsed_jobs = sample_intake.get("parsed_jobs") or []
    sow = build_sow_skeleton(
        intake={
            "applicant_name": sample_intake.get("applicant_name"),
            "preferences": sample_intake.get("preferences") or {},
        },
        parsed_jobs=parsed_jobs,
    )

    resource_match = match_resources_for_sow(sow, resource_file)
    sow["resource_plan"] = {
        "required": resource_match.get("required") or [],
        "recommended": resource_match.get("recommended") or [],
        "optional": resource_match.get("optional") or [],
    }
    sow["mentoring_cta"] = {
        "recommended_tier": ((resource_match.get("mentoring") or {}).get("tiers") or [{}])[0].get("name", "Bi-weekly 1:1"),
        "reason": "Matched to milestone tags and baseline skill targets.",
        "program_url": (resource_match.get("mentoring") or {}).get("url"),
    }

    findings = validate_sow_payload(sow)

    return {
        "generated_at": utc_now_iso(),
        "sample_intake": sample_intake,
        "parsed_jobs": parsed_jobs,
        "sow": sow,
        "validation": {
            "findings": findings,
            "valid": len(findings) == 0,
        },
        "resource_match": {
            "match_meta": resource_match.get("match_meta") or {},
            "mentoring": resource_match.get("mentoring") or {},
        },
    }
