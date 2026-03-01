from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
import json
import re

COMMON_SKILLS = {
    "python", "sql", "dbt", "airflow", "spark", "pyspark", "databricks", "snowflake",
    "aws", "azure", "gcp", "docker", "kubernetes", "terraform", "power bi", "tableau",
    "kafka", "flink", "etl", "elt", "medallion", "lakehouse", "data modeling", "ci/cd",
}

COMMON_DOMAINS = {
    "finance", "healthcare", "retail", "manufacturing", "telecom", "insurance", "saas",
    "ecommerce", "logistics", "public sector", "energy", "education",
}

COMMON_TOOLS = {
    "databricks", "snowflake", "bigquery", "redshift", "postgres", "mysql", "airflow",
    "dbt", "power bi", "tableau", "git", "github", "gitlab", "jira", "confluence",
}

TAG_TOPIC_MAP = {
    "discovery": ["career", "communication", "architecture"],
    "bronze": ["pipeline", "data-engineering", "pyspark", "spark", "databricks", "big-data"],
    "silver": ["sql", "quality", "performance", "query-optimization"],
    "gold": ["bi", "visualization", "storytelling", "warehouse", "dimensional-modeling", "star-schema"],
    "roi": ["bi", "visualization", "communication"],
    "governance": ["governance", "data-management"],
    "architecture": ["architecture", "distributed-systems", "data-platform"],
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _plain_text_from_html(body: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", body, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_job_text(url: str, timeout: int = 8) -> dict[str, Any]:
    req = urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenClaw CoachingBot)"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            ctype = str(resp.headers.get("Content-Type") or "").lower()
            decoded = raw.decode("utf-8", errors="ignore")
            if "html" in ctype or "<html" in decoded[:400].lower():
                txt = _plain_text_from_html(decoded)
            else:
                txt = decoded
            return {"ok": True, "url": url, "text": txt[:30000], "error": None}
    except HTTPError as e:
        return {"ok": False, "url": url, "text": "", "error": f"HTTPError {e.code}"}
    except URLError as e:
        return {"ok": False, "url": url, "text": "", "error": f"URLError {e.reason}"}
    except Exception as e:
        return {"ok": False, "url": url, "text": "", "error": str(e)}


def extract_job_signals(text: str) -> dict[str, Any]:
    low = (text or "").lower()

    skills = sorted([s for s in COMMON_SKILLS if s in low])
    domains = sorted([d for d in COMMON_DOMAINS if d in low])
    tools = sorted([t for t in COMMON_TOOLS if t in low])

    seniority = "mid"
    if any(w in low for w in ["principal", "staff", "lead"]):
        seniority = "senior"
    elif any(w in low for w in ["senior", "sr.", "sr "]):
        seniority = "senior"
    elif any(w in low for w in ["entry", "junior", "associate"]):
        seniority = "junior"

    return {
        "skills": skills,
        "tools": tools,
        "domains": domains,
        "seniority": seniority,
    }


def build_sow_skeleton(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    all_skills = sorted({s for p in parsed_jobs for s in p.get("signals", {}).get("skills", [])})
    all_tools = sorted({s for p in parsed_jobs for s in p.get("signals", {}).get("tools", [])})
    all_domains = sorted({s for p in parsed_jobs for s in p.get("signals", {}).get("domains", [])})

    project_title = f"{(intake.get('applicant_name') or 'Candidate')} Data Engineering Capstone"

    return {
        "schema_version": "0.2",
        "project_title": project_title,
        "candidate_profile": {
            "applicant_name": intake.get("applicant_name"),
            "preferences": intake.get("preferences") or {},
        },
        "business_outcome": {
            "problem_statement": "Define a measurable business problem and target KPI uplift.",
            "target_metrics": [
                {"metric": "pipeline_sla_minutes", "target": "<60"},
                {"metric": "dashboard_adoption_rate", "target": ">=60%"},
            ],
            "domain_focus": all_domains,
        },
        "solution_architecture": {
            "medallion_plan": {
                "bronze": "Ingest raw source data with schema drift handling.",
                "silver": "Apply cleaning, conformance, and quality checks.",
                "gold": "Publish curated marts and KPI-ready tables.",
            },
            "primary_tools": all_tools,
            "target_skills": all_skills,
        },
        "milestones": [
            {
                "name": "Discovery + Business framing",
                "duration_weeks": 1,
                "deliverables": ["scope brief", "KPI definitions"],
                "milestone_tags": ["discovery", "architecture", "roi"],
            },
            {
                "name": "Bronze/Silver implementation",
                "duration_weeks": 2,
                "deliverables": ["ingestion jobs", "DQ checks"],
                "milestone_tags": ["bronze", "silver", "pipeline"],
            },
            {
                "name": "Gold + ROI dashboard",
                "duration_weeks": 1,
                "deliverables": ["semantic model", "executive dashboard"],
                "milestone_tags": ["gold", "roi", "bi"],
            },
            {
                "name": "Final review + portfolio assets",
                "duration_weeks": 1,
                "deliverables": ["architecture narrative", "repo walkthrough"],
                "milestone_tags": ["communication", "career"],
            },
        ],
        "roi_dashboard_requirements": {
            "required_dimensions": ["time", "business_unit", "product"],
            "required_measures": ["cost_savings", "revenue_impact", "sla_compliance"],
        },
        "resource_plan": {
            "required": [],
            "recommended": [],
            "optional": [],
            "affiliate_disclosure": "Some recommended resources may include affiliate links. Recommendations are selected for project relevance first.",
            "trust_language": "Resource recommendations are optional and do not change coaching feedback or project scoring.",
        },
        "mentoring_cta": {
            "recommended_tier": "TBD",
            "reason": "Finalize after validation and skill-gap scoring.",
            "trust_language": "Mentoring recommendations are guidance-only and should align with the candidate's goals and budget.",
        },
    }


def validate_sow_payload(sow: dict[str, Any]) -> list[dict[str, str]]:
    findings: list[dict[str, str]] = []

    required_top_keys = [
        "project_title",
        "business_outcome",
        "solution_architecture",
        "milestones",
        "roi_dashboard_requirements",
        "resource_plan",
        "mentoring_cta",
    ]
    for key in required_top_keys:
        if key not in sow:
            findings.append({"code": "MISSING_SECTION", "message": f"Missing required section: {key}"})

    medallion = ((sow.get("solution_architecture") or {}).get("medallion_plan") or {})
    for layer in ["bronze", "silver", "gold"]:
        if not str(medallion.get(layer) or "").strip():
            findings.append({"code": "MEDALLION_INCOMPLETE", "message": f"Missing medallion layer detail: {layer}"})

    milestones = sow.get("milestones") or []
    if not isinstance(milestones, list) or len(milestones) < 3:
        findings.append({"code": "MILESTONE_MINIMUM", "message": "At least 3 milestones are required."})

    roi = sow.get("roi_dashboard_requirements") or {}
    if not (roi.get("required_measures") and roi.get("required_dimensions")):
        findings.append({"code": "ROI_REQUIREMENTS_MISSING", "message": "ROI dashboard measures and dimensions are required."})

    resources = sow.get("resource_plan") or {}
    total_links = sum(len(resources.get(k) or []) for k in ["required", "recommended", "optional"])
    if total_links == 0:
        findings.append({"code": "RESOURCE_LINKS_MISSING", "message": "Provide at least one resource link in resource_plan."})

    if not str(resources.get("affiliate_disclosure") or "").strip():
        findings.append({"code": "AFFILIATE_DISCLOSURE_MISSING", "message": "resource_plan.affiliate_disclosure is required for trust transparency."})

    mentoring_cta = sow.get("mentoring_cta") or {}
    if not str(mentoring_cta.get("trust_language") or "").strip():
        findings.append({"code": "TRUST_LANGUAGE_MISSING", "message": "mentoring_cta.trust_language is required."})

    return findings


def auto_revise_sow_once(sow: dict[str, Any], findings: list[dict[str, str]]) -> dict[str, Any]:
    _ = findings
    out = dict(sow)
    out.setdefault("solution_architecture", {}).setdefault("medallion_plan", {})
    med = out["solution_architecture"]["medallion_plan"]
    med.setdefault("bronze", "Raw ingestion and CDC capture.")
    med.setdefault("silver", "Conformance, quality checks, and SCD handling.")
    med.setdefault("gold", "KPI marts and executive analytics consumption layer.")

    if not out.get("milestones"):
        out["milestones"] = [
            {"name": "Planning", "duration_weeks": 1, "deliverables": ["scope"], "milestone_tags": ["discovery"]},
            {"name": "Build", "duration_weeks": 2, "deliverables": ["pipelines"], "milestone_tags": ["bronze", "silver"]},
            {"name": "Report", "duration_weeks": 1, "deliverables": ["dashboard"], "milestone_tags": ["gold", "roi"]},
        ]

    out.setdefault("roi_dashboard_requirements", {})
    out["roi_dashboard_requirements"].setdefault("required_dimensions", ["time", "business_unit"])
    out["roi_dashboard_requirements"].setdefault("required_measures", ["cost_savings"])

    out.setdefault("resource_plan", {})
    out["resource_plan"].setdefault("required", [{"title": "Project README Template", "url": "https://example.com/readme-template"}])
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


def _load_resource_library(resource_file: str | Path) -> dict[str, Any]:
    return json.loads(Path(resource_file).read_text(encoding="utf-8"))


def _resource_topics(resource: dict[str, Any]) -> set[str]:
    return {str(t).strip().lower() for t in (resource.get("topics") or []) if str(t).strip()}


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
