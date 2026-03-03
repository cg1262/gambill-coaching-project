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

REQUIRED_SECTION_FLOW = [
    "schema_version",
    "project_title",
    "candidate_profile",
    "business_outcome",
    "solution_architecture",
    "project_story",
    "milestones",
    "roi_dashboard_requirements",
    "resource_plan",
    "mentoring_cta",
]


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


def _mask_if_str(value: Any) -> Any:
    return mask_secrets_in_text(value) if isinstance(value, str) else value


def sanitize_generated_sow(sow: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    out = json.loads(json.dumps(sow or {}))
    findings: list[dict[str, str]] = []

    for narrative_key in ["project_title", "project_story"]:
        if narrative_key in out:
            out[narrative_key] = _mask_if_str(out.get(narrative_key))

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

    business_outcome = out.get("business_outcome") or {}
    for text_key in ["problem_statement", "target_users", "success_metric", "constraints"]:
        if text_key in business_outcome:
            business_outcome[text_key] = _mask_if_str(business_outcome.get(text_key))
    out["business_outcome"] = business_outcome

    for ms in (out.get("milestones") or []):
        if not isinstance(ms, dict):
            continue
        for text_key in ["name", "execution_plan", "expected_deliverable", "business_why"]:
            if text_key in ms:
                ms[text_key] = _mask_if_str(ms.get(text_key))
        if isinstance(ms.get("deliverables"), list):
            ms["deliverables"] = [_mask_if_str(x) for x in (ms.get("deliverables") or [])]

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
            "top_level_required": list(REQUIRED_SECTION_FLOW),
            "top_level_order_required": list(REQUIRED_SECTION_FLOW),
            "section_flow": [
                "project_title -> candidate profile context",
                "business_outcome -> measurable KPI targets + public data sources",
                "solution_architecture -> medallion implementation plan",
                "project_story -> executive narrative (summary, challenge, approach, impact)",
                "milestones -> execution_plan + expected_deliverable + business_why",
                "roi_dashboard_requirements -> dimensions + measures",
                "resource_plan -> required/recommended/optional links + trust language",
                "mentoring_cta -> optional personalized recommendation language",
            ],
            "business_outcome_required": ["problem_statement", "target_metrics", "domain_focus", "data_sources"],
            "data_source_shape": {"name": "string", "url": "https://real-link", "ingestion_doc_url": "https://real-doc-link"},
            "milestone_shape": {
                "name": "string", "duration_weeks": "int>=1", "deliverables": ["string"],
                "execution_plan": "string", "expected_deliverable": "string", "business_why": "string",
                "milestone_tags": ["string"], "resources": [{"title": "string", "url": "https://real-link"}],
            },
            "project_story_required": ["executive_summary", "challenge", "approach", "impact_story"],
            "roi_required": ["required_dimensions", "required_measures"],
            "resources_required": ["required", "recommended", "optional", "affiliate_disclosure", "trust_language"],
            "hard_rules": [
                "Return JSON only, no markdown",
                "Mirror exemplar section sequence and flow exactly using top_level_order_required",
                "Keep content personalized to candidate resume/preferences/target roles (no generic placeholder narrative)",
                "Use real non-placeholder URLs",
                "At least 3 milestones",
                "Each milestone must include execution_plan, expected_deliverable, and business_why",
                "Each milestone must include at least one resource link",
                "Include at least one concrete public data source URL",
                "Include at least one ingestion documentation URL",
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
                "content": "You are a senior data engineering consulting partner. Produce production-grade SOW JSON following the required contract exactly. The top-level section order must mirror the exemplar flow exactly, while all narrative content remains personalized to the candidate context. For each milestone, provide concrete execution details (what to do), explicit expected deliverable quality, and business rationale that ties work to measurable outcomes.",
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
            structure = evaluate_sow_structure(sow)
            if structure.get("missing_sections") or not structure.get("order_valid"):
                last_error = "LLM output failed required structure contract"
                error_type = "schema"
                if attempts <= max_retries:
                    continue
                break
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


DATA_SOURCE_CANDIDATES: list[dict[str, Any]] = [
    {
        "name": "NYC TLC Trip Record Data",
        "url": "https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page",
        "ingestion_doc_url": "https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf",
        "tags": {"transport", "analytics", "sql", "power bi"},
        "selection_rationale": "Public trip-level facts are excellent for building medallion pipelines and KPI reporting exercises.",
    },
    {
        "name": "Bureau of Labor Statistics Public Data API",
        "url": "https://www.bls.gov/data/",
        "ingestion_doc_url": "https://www.bls.gov/developers/home.htm",
        "tags": {"economics", "api", "python", "time-series"},
        "selection_rationale": "Provides real API ingestion practice plus documented schemas for incremental loads and trend dashboards.",
    },
    {
        "name": "NYC Open Data (Socrata)",
        "url": "https://opendata.cityofnewyork.us/",
        "ingestion_doc_url": "https://dev.socrata.com/docs/",
        "tags": {"api", "etl", "governance", "data quality"},
        "selection_rationale": "Offers diverse public datasets with API docs suited for data quality checks and stakeholder-facing reporting.",
    },
    {
        "name": "Chicago Data Portal",
        "url": "https://data.cityofchicago.org/",
        "ingestion_doc_url": "https://dev.socrata.com/foundry/data.cityofchicago.org",
        "tags": {"city", "public", "dashboard", "bi"},
        "selection_rationale": "Good source for reproducible city analytics projects with clear ingestion endpoints and metadata.",
    },
]


def _select_data_sources(intake: dict[str, Any], parsed_jobs: list[dict[str, Any]], limit: int = 3) -> list[dict[str, str]]:
    preference_terms = {
        str(x).strip().lower()
        for x in (
            (intake.get("preferences") or {}).get("stack") or []
        )
        if str(x).strip()
    }
    for key in ["tool_preferences", "stack_preferences"]:
        for term in ((intake.get("preferences") or {}).get(key) or []):
            if str(term).strip():
                preference_terms.add(str(term).strip().lower())

    job_terms = {
        str(x).strip().lower()
        for p in (parsed_jobs or [])
        for bucket in ["skills", "tools", "domains"]
        for x in ((p.get("signals") or {}).get(bucket) or [])
        if str(x).strip()
    }
    terms = preference_terms | job_terms

    scored: list[tuple[int, dict[str, Any]]] = []
    for candidate in DATA_SOURCE_CANDIDATES:
        tags = {str(t).strip().lower() for t in (candidate.get("tags") or set()) if str(t).strip()}
        score = len(tags & terms)
        scored.append((score, candidate))

    scored.sort(key=lambda row: (-row[0], str(row[1].get("name") or "")))
    chosen: list[dict[str, str]] = []
    for _, candidate in scored[: max(1, int(limit))]:
        chosen.append(
            {
                "name": str(candidate.get("name") or ""),
                "url": str(candidate.get("url") or ""),
                "ingestion_doc_url": str(candidate.get("ingestion_doc_url") or ""),
                "selection_rationale": str(candidate.get("selection_rationale") or "Selected for relevance to target project outcomes."),
            }
        )
    return chosen


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
            "data_sources": _select_data_sources(intake=intake, parsed_jobs=parsed_jobs),
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
                "execution_plan": "Interview stakeholders, map source systems, and define KPI ownership with acceptance criteria.",
                "expected_deliverable": "Signed project charter with KPI dictionary, source inventory, and scope boundaries approved by sponsor.",
                "business_why": "Aligning scope and KPI definitions early prevents rework and accelerates measurable ROI delivery.",
                "milestone_tags": ["discovery", "architecture", "roi"],
                "resources": [{"title": "Kimball Dimensional Modeling", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"}],
            },
            {
                "name": "Bronze/Silver implementation",
                "duration_weeks": 2,
                "deliverables": ["ingestion jobs", "DQ checks"],
                "execution_plan": "Build incremental ingestion pipelines, apply schema evolution handling, and implement automated data quality gates.",
                "expected_deliverable": "Production-ready bronze/silver DAGs with tests, monitoring, and documented failure handling.",
                "business_why": "Reliable ingestion and conformance reduce reporting defects and improve trust in downstream analytics.",
                "milestone_tags": ["bronze", "silver", "pipeline"],
                "resources": [{"title": "Delta Lake Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"}],
            },
            {
                "name": "Gold + ROI dashboard",
                "duration_weeks": 1,
                "deliverables": ["semantic model", "executive dashboard"],
                "execution_plan": "Model gold marts for executive questions, define semantic layer metrics, and build ROI dashboard narratives.",
                "expected_deliverable": "Validated KPI dashboard with traceable metric definitions and stakeholder walkthrough recording.",
                "business_why": "Clear KPI visibility enables faster decisions and proves business impact of the data platform investment.",
                "milestone_tags": ["gold", "roi", "bi"],
                "resources": [{"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}],
            },
            {
                "name": "Final review + portfolio assets",
                "duration_weeks": 1,
                "deliverables": ["architecture narrative", "repo walkthrough"],
                "execution_plan": "Package architecture decisions, demo script, and retrospective into a portfolio-quality delivery artifact set.",
                "expected_deliverable": "Publish-ready repo and presentation assets that communicate technical depth and business outcomes.",
                "business_why": "Strong communication artifacts increase hiring signal and stakeholder confidence in project value.",
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


def evaluate_sow_structure(sow: dict[str, Any]) -> dict[str, Any]:
    payload = sow or {}
    expected = list(REQUIRED_SECTION_FLOW)
    missing_sections = [section for section in expected if section not in payload]
    actual_sequence = [key for key in payload.keys() if key in expected]
    expected_sequence = [section for section in expected if section in payload]

    order_valid = actual_sequence == expected_sequence
    out_of_order_sections: list[str] = []
    if not order_valid:
        for index, section in enumerate(actual_sequence):
            if index >= len(expected_sequence) or section != expected_sequence[index]:
                out_of_order_sections.append(section)

    structure_score = int(((len(expected) - len(missing_sections)) / len(expected)) * 100)
    if not order_valid:
        structure_score = max(0, structure_score - (10 * max(1, len(out_of_order_sections))))

    return {
        "expected_sequence": expected,
        "actual_sequence": actual_sequence,
        "order_valid": order_valid,
        "missing_sections": missing_sections,
        "out_of_order_sections": out_of_order_sections,
        "structure_score": max(0, min(100, structure_score)),
        "structure_valid": (len(missing_sections) == 0 and order_valid),
    }


def validate_sow_payload(sow: dict[str, Any]) -> list[dict[str, str]]:
    sow, safety_findings = sanitize_generated_sow(sow)
    findings: list[dict[str, str]] = list(safety_findings)

    structure = evaluate_sow_structure(sow)
    for key in structure.get("missing_sections") or []:
        findings.append({"code": "MISSING_SECTION", "message": f"Missing required section: {key}"})
    if not structure.get("order_valid"):
        findings.append(
            {
                "code": "SECTION_ORDER_INVALID",
                "message": "Top-level sections are out of order. Follow REQUIRED_SECTION_FLOW.",
            }
        )

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
    concrete_source_links = 0
    ingestion_doc_links = 0
    for i, ds in enumerate(data_sources):
        if _is_valid_non_placeholder_url(str(ds.get("url") or "")):
            concrete_source_links += 1
        else:
            findings.append({"code": "DATA_SOURCE_LINK_INVALID", "message": f"data_sources[{i}].url must be a real link."})
        if _is_valid_non_placeholder_url(str(ds.get("ingestion_doc_url") or "")):
            ingestion_doc_links += 1
        else:
            findings.append({"code": "INGESTION_DOC_LINK_MISSING", "message": f"data_sources[{i}].ingestion_doc_url must be a real link."})
        if not str(ds.get("selection_rationale") or "").strip():
            findings.append({"code": "DATA_SOURCE_RATIONALE_MISSING", "message": f"data_sources[{i}].selection_rationale is required."})
    if concrete_source_links < 1:
        findings.append({"code": "DATA_SOURCE_PUBLIC_LINK_REQUIRED", "message": "At least one concrete public data source URL is required."})
    if ingestion_doc_links < 1:
        findings.append({"code": "DATA_SOURCE_INGESTION_DOC_REQUIRED", "message": "At least one ingestion documentation URL is required."})

    milestones = sow.get("milestones") or []
    if not isinstance(milestones, list) or len(milestones) < 3:
        findings.append({"code": "MILESTONE_MINIMUM", "message": "At least 3 milestones are required."})
    else:
        for i, ms in enumerate(milestones):
            if not str(ms.get("execution_plan") or "").strip():
                findings.append({"code": "MILESTONE_EXECUTION_PLAN_MISSING", "message": f"milestones[{i}].execution_plan is required."})
            if not str(ms.get("expected_deliverable") or "").strip():
                findings.append({"code": "MILESTONE_EXPECTED_DELIVERABLE_MISSING", "message": f"milestones[{i}].expected_deliverable is required."})
            if not str(ms.get("business_why") or "").strip():
                findings.append({"code": "MILESTONE_BUSINESS_WHY_MISSING", "message": f"milestones[{i}].business_why is required."})
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
    structure = evaluate_sow_structure(sow)
    penalties = min(80, len(issues) * 8)
    content_score = max(0, min(100, 100 - penalties))
    score = int(round((0.7 * content_score) + (0.3 * int(structure.get("structure_score") or 0))))
    return {
        "score": score,
        "threshold_passed": score >= 70,
        "finding_count": len(issues),
        "structure_score": int(structure.get("structure_score") or 0),
        "missing_sections": structure.get("missing_sections") or [],
        "section_order_valid": bool(structure.get("order_valid")),
    }


def build_quality_diagnostics(quality: dict[str, Any], findings: list[dict[str, str]], floor_score: int = 80, auto_regenerated: bool = False) -> dict[str, Any]:
    score = int(quality.get("score") or 0)
    codes = [str(f.get("code") or "") for f in findings if str(f.get("code") or "")]
    return {
        "floor_score": floor_score,
        "score": score,
        "below_floor": score < int(floor_score),
        "auto_regenerated": bool(auto_regenerated),
        "deficiency_codes": sorted(set(codes)),
        "deficiency_count": len(findings),
        "top_deficiencies": [f.get("message") for f in findings[:5]],
        "structure_score": int(quality.get("structure_score") or 0),
        "missing_sections": quality.get("missing_sections") or [],
        "section_order_valid": bool(quality.get("section_order_valid")),
    }


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
                "selection_rationale": "Public API-backed labor data supports robust ingestion and KPI storytelling without private data dependencies.",
            }
        ]

    for ds in (out.get("business_outcome") or {}).get("data_sources") or []:
        if isinstance(ds, dict) and not str(ds.get("selection_rationale") or "").strip():
            ds["selection_rationale"] = "Selected as a public, documentation-backed source aligned to the target business outcome and delivery timeline."

    if not out.get("milestones"):
        out["milestones"] = [
            {"name": "Planning", "duration_weeks": 1, "deliverables": ["scope"], "milestone_tags": ["discovery"], "resources": [{"title": "Discovery checklist", "url": "https://www.atlassian.com/software/jira/guides"}]},
            {"name": "Build", "duration_weeks": 2, "deliverables": ["pipelines"], "milestone_tags": ["bronze", "silver"], "resources": [{"title": "Airflow docs", "url": "https://airflow.apache.org/docs/"}]},
            {"name": "Report", "duration_weeks": 1, "deliverables": ["dashboard"], "milestone_tags": ["gold", "roi"], "resources": [{"title": "Looker modeling", "url": "https://cloud.google.com/looker/docs"}]},
        ]
    for ms in (out.get("milestones") or []):
        if not str(ms.get("execution_plan") or "").strip():
            ms["execution_plan"] = "Break work into implementation tasks, owners, and checkpoints with explicit acceptance criteria."
        if not str(ms.get("expected_deliverable") or "").strip():
            ms["expected_deliverable"] = "Deliverable is complete, validated, and demo-ready with reproducible evidence."
        if not str(ms.get("business_why") or "").strip():
            ms["business_why"] = "Milestone output should improve delivery speed, trust, or measurable business value."
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
