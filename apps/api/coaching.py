from __future__ import annotations

from datetime import datetime, timezone
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
        "schema_version": "0.1",
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
            {"name": "Discovery + Business framing", "duration_weeks": 1, "deliverables": ["scope brief", "KPI definitions"]},
            {"name": "Bronze/Silver implementation", "duration_weeks": 2, "deliverables": ["ingestion jobs", "DQ checks"]},
            {"name": "Gold + ROI dashboard", "duration_weeks": 1, "deliverables": ["semantic model", "executive dashboard"]},
            {"name": "Final review + portfolio assets", "duration_weeks": 1, "deliverables": ["architecture narrative", "repo walkthrough"]},
        ],
        "roi_dashboard_requirements": {
            "required_dimensions": ["time", "business_unit", "product"],
            "required_measures": ["cost_savings", "revenue_impact", "sla_compliance"],
        },
        "resource_plan": {
            "required": [],
            "recommended": [],
            "optional": [],
        },
        "mentoring_cta": {
            "recommended_tier": "TBD",
            "reason": "Finalize after validation and skill-gap scoring.",
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

    return findings


def auto_revise_sow_once(sow: dict[str, Any], findings: list[dict[str, str]]) -> dict[str, Any]:
    out = dict(sow)
    out.setdefault("solution_architecture", {}).setdefault("medallion_plan", {})
    med = out["solution_architecture"]["medallion_plan"]
    med.setdefault("bronze", "Raw ingestion and CDC capture.")
    med.setdefault("silver", "Conformance, quality checks, and SCD handling.")
    med.setdefault("gold", "KPI marts and executive analytics consumption layer.")

    if not out.get("milestones"):
        out["milestones"] = [
            {"name": "Planning", "duration_weeks": 1, "deliverables": ["scope"]},
            {"name": "Build", "duration_weeks": 2, "deliverables": ["pipelines"]},
            {"name": "Report", "duration_weeks": 1, "deliverables": ["dashboard"]},
        ]

    out.setdefault("roi_dashboard_requirements", {})
    out["roi_dashboard_requirements"].setdefault("required_dimensions", ["time", "business_unit"])
    out["roi_dashboard_requirements"].setdefault("required_measures", ["cost_savings"])

    out.setdefault("resource_plan", {})
    out["resource_plan"].setdefault("required", [{"title": "Project README Template", "url": "https://example.com/readme-template"}])
    out["resource_plan"].setdefault("recommended", [])
    out["resource_plan"].setdefault("optional", [])

    return out
