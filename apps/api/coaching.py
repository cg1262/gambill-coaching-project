from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import json
import os
import re
import socket
import ipaddress

from security import mask_secrets_in_text

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


def _is_private_or_loopback_host(host: str) -> bool:
    value = str(host or "").strip().lower()
    if not value:
        return True
    if value in {"localhost", "127.0.0.1", "::1"}:
        return True
    try:
        ip = ipaddress.ip_address(value)
        return bool(ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved)
    except ValueError:
        pass
    try:
        infos = socket.getaddrinfo(value, None)
    except Exception:
        return True
    for info in infos:
        ip_txt = str(info[4][0])
        try:
            ip = ipaddress.ip_address(ip_txt)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                return True
        except ValueError:
            return True
    return False


def _validate_safe_url(url: str) -> tuple[bool, str | None]:
    raw = str(url or "").strip()
    if not raw:
        return False, "missing_url"
    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"javascript", "data"}:
        return False, f"blocked_scheme:{scheme}"
    if scheme not in {"http", "https"}:
        return False, f"unsupported_scheme:{scheme or 'none'}"
    if not parsed.netloc:
        return False, "missing_host"
    if _is_private_or_loopback_host(parsed.hostname or ""):
        return False, "blocked_private_host"
    return True, None


def sanitize_generated_sow(sow: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    out = json.loads(json.dumps(sow or {}))
    findings: list[dict[str, str]] = []

    resources = out.get("resource_plan") or {}
    for bucket in ["required", "recommended", "optional"]:
        cleaned_items = []
        for item in (resources.get(bucket) or []):
            if not isinstance(item, dict):
                continue
            row = dict(item)
            if isinstance(row.get("title"), str):
                row["title"] = mask_secrets_in_text(row["title"])
            if isinstance(row.get("reason"), str):
                row["reason"] = mask_secrets_in_text(row["reason"])
            ok, reason = _validate_safe_url(str(row.get("url") or ""))
            if not ok:
                findings.append(
                    {
                        "code": "UNSAFE_RESOURCE_URL",
                        "message": f"Blocked unsafe resource_plan.{bucket} URL ({reason}).",
                    }
                )
                row["url"] = ""
                row["safety_flag"] = "blocked_unsafe_url"
            cleaned_items.append(row)
        resources[bucket] = cleaned_items

    for text_key in ["affiliate_disclosure", "trust_language"]:
        if isinstance(resources.get(text_key), str):
            resources[text_key] = mask_secrets_in_text(resources[text_key])
    out["resource_plan"] = resources

    mentoring = out.get("mentoring_cta") or {}
    for text_key in ["reason", "offer", "pricing", "timeline", "cta_text", "trust_language"]:
        if isinstance(mentoring.get(text_key), str):
            mentoring[text_key] = mask_secrets_in_text(mentoring[text_key])
    if "program_url" in mentoring:
        ok, reason = _validate_safe_url(str(mentoring.get("program_url") or ""))
        if not ok:
            findings.append({"code": "UNSAFE_PROGRAM_URL", "message": f"Blocked unsafe mentoring_cta.program_url ({reason})."})
            mentoring["program_url"] = ""
            mentoring["safety_flag"] = "blocked_unsafe_url"
    out["mentoring_cta"] = mentoring

    return out, findings


def _plain_text_from_html(body: str) -> str:
    text = re.sub(r"<script[\\s\\S]*?</script>", " ", body, flags=re.IGNORECASE)
    text = re.sub(r"<style[\\s\\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_job_text(url: str, timeout: int = 8) -> dict[str, Any]:
    ok, reason = _validate_safe_url(url)
    if not ok:
        return {"ok": False, "url": url, "text": "", "error": f"Unsafe URL blocked ({reason})"}

    req = urlrequest.Request(url, headers={"User-Agent": "Mozilla/5.0 (OpenClaw CoachingBot)"})
    try:
        with urlrequest.urlopen(req, timeout=timeout) as resp:
            raw = resp.read(2 * 1024 * 1024)
            ctype = str(resp.headers.get("Content-Type") or "").lower()
            if ctype and not any(x in ctype for x in ["html", "text", "json", "xml"]):
                return {"ok": False, "url": url, "text": "", "error": f"Unsupported content type: {ctype}"}
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


def _is_valid_non_placeholder_url(url: str) -> bool:
    s = str(url or "").strip().lower()
    if not (s.startswith("http://") or s.startswith("https://")):
        return False
    blocked = ["example.com", "localhost", "127.0.0.1", "placeholder", "your-link", "tbd"]
    return not any(b in s for b in blocked)


def _safe_json_loads(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = text.rstrip("`").strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        text = text[start : end + 1]
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object")
    return parsed


def generate_sow_with_llm(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
    timeout: int = 45,
    max_retries: int = 2,
) -> dict[str, Any]:
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    model = (os.getenv("COACHING_SOW_LLM_MODEL") or "gpt-4o-mini").strip()
    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")

    if not api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY missing",
            "sow": build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs),
            "meta": {"provider": "scaffold", "model": "fallback", "base_url": base_url},
        }

    prompt_payload = {
        "candidate": {
            "name": intake.get("applicant_name"),
            "preferences": intake.get("preferences") or {},
            "resume_text": str(intake.get("resume_text") or "")[:4000],
            "self_assessment_text": str(intake.get("self_assessment_text") or "")[:4000],
        },
        "parsed_jobs": parsed_jobs[:8],
        "required_contract": {
            "top_level_required": [
                "schema_version", "project_title", "candidate_profile", "business_outcome",
                "solution_architecture", "project_story", "milestones", "roi_dashboard_requirements",
                "resource_plan", "mentoring_cta",
            ],
            "business_outcome_required": ["problem_statement", "target_metrics", "domain_focus", "data_sources"],
            "data_source_shape": {"name": "string", "url": "https://real-link", "ingestion_doc_url": "https://real-doc-link"},
            "milestone_shape": {
                "name": "string", "duration_weeks": "int>=1", "deliverables": ["string"],
                "milestone_tags": ["string"], "resources": [{"title": "string", "url": "https://real-link"}],
            },
            "project_story_required": ["executive_summary", "challenge", "approach", "impact_story"],
            "roi_required": ["required_dimensions", "required_measures"],
            "resources_required": ["required", "recommended", "optional", "affiliate_disclosure", "trust_language"],
            "hard_rules": [
                "Return JSON only, no markdown",
                "Use real non-placeholder URLs",
                "At least 3 milestones",
                "Each milestone must include at least one resource link",
                "Every data source must include ingestion_doc_url",
            ],
        },
    }

    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior data engineering consulting partner. Produce production-grade SOW JSON following the required contract exactly.",
            },
            {"role": "user", "content": json.dumps(prompt_payload)},
        ],
        "response_format": {"type": "json_object"},
    }
    req = urlrequest.Request(
        f"{base_url}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    attempts = 0
    last_error = "unknown_error"
    error_type = "provider"
    while attempts <= max_retries:
        attempts += 1
        try:
            with urlrequest.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))
            content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
            sow = _safe_json_loads(content)
            return {
                "ok": True,
                "sow": sow,
                "meta": {
                    "provider": "openai-compatible",
                    "model": model,
                    "base_url": base_url,
                    "usage": payload.get("usage") or {},
                    "finish_reason": (((payload.get("choices") or [{}])[0].get("finish_reason")) or ""),
                    "attempts": attempts,
                    "error_type": None,
                },
            }
        except HTTPError as e:
            last_error = f"HTTPError {e.code}"
            error_type = "provider"
            if e.code < 500 and e.code not in {408, 429}:
                break
        except URLError as e:
            last_error = f"URLError {e.reason}"
            error_type = "network"
        except TimeoutError as e:
            last_error = str(e) or "timeout"
            error_type = "timeout"
        except json.JSONDecodeError as e:
            last_error = str(e)
            error_type = "schema"
            break
        except Exception as e:
            last_error = str(e)
            error_type = "provider"
        if attempts > max_retries:
            break

    return {
        "ok": False,
        "error": last_error,
        "sow": build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs),
        "meta": {
            "provider": "scaffold",
            "model": "fallback",
            "base_url": base_url,
            "attempts": attempts,
            "error_type": error_type,
        },
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
            "data_sources": [
                {
                    "name": "NYC TLC Trip Record Data",
                    "url": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
                    "ingestion_doc_url": "https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf",
                }
            ],
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
        "project_story": {
            "executive_summary": "Build a job-aligned medallion data platform project with measurable business outcomes and portfolio-ready artifacts.",
            "challenge": "Translate fragmented source data into trusted KPI reporting under tight delivery timelines.",
            "approach": "Implement bronze/silver/gold pipelines, data quality checks, and executive-friendly ROI dashboards.",
            "impact_story": "Demonstrate end-to-end ownership from ingestion through business narrative and stakeholder-ready metrics.",
        },
        "milestones": [
            {
                "name": "Discovery + Business framing",
                "duration_weeks": 1,
                "deliverables": ["scope brief", "KPI definitions"],
                "milestone_tags": ["discovery", "architecture", "roi"],
                "resources": [{"title": "Kimball Dimensional Modeling", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"}],
            },
            {
                "name": "Bronze/Silver implementation",
                "duration_weeks": 2,
                "deliverables": ["ingestion jobs", "DQ checks"],
                "milestone_tags": ["bronze", "silver", "pipeline"],
                "resources": [{"title": "Delta Lake Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"}],
            },
            {
                "name": "Gold + ROI dashboard",
                "duration_weeks": 1,
                "deliverables": ["semantic model", "executive dashboard"],
                "milestone_tags": ["gold", "roi", "bi"],
                "resources": [{"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}],
            },
            {
                "name": "Final review + portfolio assets",
                "duration_weeks": 1,
                "deliverables": ["architecture narrative", "repo walkthrough"],
                "milestone_tags": ["communication", "career"],
                "resources": [{"title": "GitHub Portfolio Guide", "url": "https://docs.github.com/en/get-started/showcase-your-work/about-your-profile"}],
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
    sow, safety_findings = sanitize_generated_sow(sow)
    findings: list[dict[str, str]] = list(safety_findings)

    required_top_keys = [
        "project_title",
        "business_outcome",
        "solution_architecture",
        "project_story",
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

    story = sow.get("project_story") or {}
    for k in ["executive_summary", "challenge", "approach", "impact_story"]:
        if not str(story.get(k) or "").strip():
            findings.append({"code": "PROJECT_STORY_MISSING", "message": f"project_story.{k} is required."})

    business = sow.get("business_outcome") or {}
    data_sources = business.get("data_sources") or []
    if not isinstance(data_sources, list) or len(data_sources) == 0:
        findings.append({"code": "DATA_SOURCES_MISSING", "message": "business_outcome.data_sources must include at least one source."})
    for i, ds in enumerate(data_sources):
        if not _is_valid_non_placeholder_url(str(ds.get("url") or "")):
            findings.append({"code": "DATA_SOURCE_LINK_INVALID", "message": f"data_sources[{i}].url must be a real link."})
        if not _is_valid_non_placeholder_url(str(ds.get("ingestion_doc_url") or "")):
            findings.append({"code": "INGESTION_DOC_LINK_MISSING", "message": f"data_sources[{i}].ingestion_doc_url must be a real link."})

    milestones = sow.get("milestones") or []
    if not isinstance(milestones, list) or len(milestones) < 3:
        findings.append({"code": "MILESTONE_MINIMUM", "message": "At least 3 milestones are required."})
    else:
        for i, ms in enumerate(milestones):
            ms_resources = ms.get("resources") or []
            if not isinstance(ms_resources, list) or len(ms_resources) == 0:
                findings.append({"code": "MILESTONE_RESOURCES_MISSING", "message": f"milestones[{i}] must include resources."})
            else:
                for j, r in enumerate(ms_resources):
                    if not _is_valid_non_placeholder_url(str(r.get("url") or "")):
                        findings.append({"code": "MILESTONE_RESOURCE_LINK_INVALID", "message": f"milestones[{i}].resources[{j}].url must be a real link."})

    roi = sow.get("roi_dashboard_requirements") or {}
    if not (roi.get("required_measures") and roi.get("required_dimensions")):
        findings.append({"code": "ROI_REQUIREMENTS_MISSING", "message": "ROI dashboard measures and dimensions are required."})

    resources = sow.get("resource_plan") or {}
    total_links = sum(len(resources.get(k) or []) for k in ["required", "recommended", "optional"])
    if total_links == 0:
        findings.append({"code": "RESOURCE_LINKS_MISSING", "message": "Provide at least one resource link in resource_plan."})
    for bucket in ["required", "recommended", "optional"]:
        for idx, item in enumerate(resources.get(bucket) or []):
            if not _is_valid_non_placeholder_url(str(item.get("url") or "")):
                findings.append({"code": "RESOURCE_LINK_INVALID", "message": f"resource_plan.{bucket}[{idx}].url must be a real link."})

    if not str(resources.get("affiliate_disclosure") or "").strip():
        findings.append({"code": "AFFILIATE_DISCLOSURE_MISSING", "message": "resource_plan.affiliate_disclosure is required for trust transparency."})

    mentoring_cta = sow.get("mentoring_cta") or {}
    if not str(mentoring_cta.get("trust_language") or "").strip():
        findings.append({"code": "TRUST_LANGUAGE_MISSING", "message": "mentoring_cta.trust_language is required."})

    return findings


def compute_sow_quality_score(sow: dict[str, Any], findings: list[dict[str, str]] | None = None) -> dict[str, Any]:
    issues = findings if findings is not None else validate_sow_payload(sow)
    penalties = min(80, len(issues) * 8)
    required_sections = [
        "project_title",
        "business_outcome",
        "solution_architecture",
        "project_story",
        "milestones",
        "roi_dashboard_requirements",
        "resource_plan",
        "mentoring_cta",
    ]
    present = sum(1 for k in required_sections if k in (sow or {}))
    completeness = int((present / len(required_sections)) * 20)
    score = max(0, min(100, completeness + (80 - penalties)))
    return {"score": score, "threshold_passed": score >= 70, "finding_count": len(issues)}


def auto_revise_sow_once(sow: dict[str, Any], findings: list[dict[str, str]]) -> dict[str, Any]:
    _ = findings
    out = dict(sow)
    out.setdefault("solution_architecture", {}).setdefault("medallion_plan", {})
    med = out["solution_architecture"]["medallion_plan"]
    med.setdefault("bronze", "Raw ingestion and CDC capture.")
    med.setdefault("silver", "Conformance, quality checks, and SCD handling.")
    med.setdefault("gold", "KPI marts and executive analytics consumption layer.")

    out.setdefault("project_story", {})
    out["project_story"].setdefault("executive_summary", "This project builds an end-to-end portfolio-ready data product.")
    out["project_story"].setdefault("challenge", "Source systems are inconsistent and require governance before business reporting.")
    out["project_story"].setdefault("approach", "Implement medallion layers, DQ checks, and stakeholder-aligned KPI modeling.")
    out["project_story"].setdefault("impact_story", "The candidate demonstrates measurable outcomes and technical leadership.")

    out.setdefault("business_outcome", {})
    if not (out["business_outcome"].get("data_sources") or []):
        out["business_outcome"]["data_sources"] = [
            {
                "name": "US Bureau of Labor Statistics",
                "url": "https://www.bls.gov/data/",
                "ingestion_doc_url": "https://www.bls.gov/developers/home.htm",
            }
        ]

    if not out.get("milestones"):
        out["milestones"] = [
            {"name": "Planning", "duration_weeks": 1, "deliverables": ["scope"], "milestone_tags": ["discovery"], "resources": [{"title": "Discovery checklist", "url": "https://www.atlassian.com/software/jira/guides"}]},
            {"name": "Build", "duration_weeks": 2, "deliverables": ["pipelines"], "milestone_tags": ["bronze", "silver"], "resources": [{"title": "Airflow docs", "url": "https://airflow.apache.org/docs/"}]},
            {"name": "Report", "duration_weeks": 1, "deliverables": ["dashboard"], "milestone_tags": ["gold", "roi"], "resources": [{"title": "Looker modeling", "url": "https://cloud.google.com/looker/docs"}]},
        ]
    for ms in (out.get("milestones") or []):
        if not (ms.get("resources") or []):
            ms["resources"] = [{"title": "Project delivery best practices", "url": "https://www.pmi.org/learning/library"}]

    out.setdefault("roi_dashboard_requirements", {})
    out["roi_dashboard_requirements"].setdefault("required_dimensions", ["time", "business_unit"])
    out["roi_dashboard_requirements"].setdefault("required_measures", ["cost_savings"])

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
