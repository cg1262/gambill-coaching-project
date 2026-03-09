from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import httpx

from .constants import (
    REQUIRED_SECTION_FLOW,
    CHARTER_REQUIRED_SECTION_FLOW,
    DATA_SOURCE_CANDIDATES,
    STYLE_ANCHORS,
)
from .sow_validation import evaluate_sow_structure, _build_interview_ready_package


def _bounded_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(minimum, min(maximum, parsed))


def _deterministic_majority(values: list[str], default: str) -> str:
    if not values:
        return default
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return ordered[0][0] if ordered else default


def _derive_scope_profile(intake: dict[str, Any], parsed_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    prefs = intake.get("preferences") or {}
    resume_summary = (prefs.get("resume_parse_summary") or {}) if isinstance(prefs, dict) else {}

    role_level = str(resume_summary.get("role_level") or "mid").strip().lower()
    if role_level not in {"junior", "mid", "senior"}:
        role_level = "mid"

    years_hint = _bounded_int(resume_summary.get("years_experience_hint"), default=0, minimum=0, maximum=40)
    parse_conf = _bounded_int(resume_summary.get("parse_confidence"), default=0, minimum=0, maximum=100)

    tools = [str(t).strip().lower() for t in (resume_summary.get("tools") or []) if str(t).strip()]
    domains = [str(d).strip().lower() for d in (resume_summary.get("domains") or []) if str(d).strip()]
    project_keywords = [str(k).strip().lower() for k in (resume_summary.get("project_experience_keywords") or []) if str(k).strip()]
    tool_count = len(set(tools))
    domain_count = len(set(domains))
    project_signal_count = len(set(project_keywords))

    seniority_votes = [str((job.get("signals") or {}).get("seniority") or "").strip().lower() for job in (parsed_jobs or [])]
    seniority_votes = [v for v in seniority_votes if v in {"junior", "mid", "senior"}]
    target_seniority = _deterministic_majority(seniority_votes, default=role_level)

    capability_index = (tool_count * 2) + domain_count + project_signal_count
    difficulty = "standard"
    if role_level == "junior" or years_hint <= 2 or parse_conf < 45:
        difficulty = "foundational"
    elif target_seniority == "senior" and role_level in {"mid", "senior"} and years_hint >= 5 and capability_index >= 14 and parse_conf >= 60:
        difficulty = "advanced"

    suggested_weeks = 6
    if difficulty == "foundational":
        suggested_weeks = 8 if parse_conf < 60 else 7
    elif difficulty == "advanced":
        suggested_weeks = 5

    if years_hint >= 10 and difficulty == "advanced" and parse_conf >= 80:
        suggested_weeks = 4

    preferred_timeline = (prefs.get("timeline_weeks") if isinstance(prefs, dict) else None)
    if preferred_timeline is not None:
        preferred = _bounded_int(preferred_timeline, default=suggested_weeks, minimum=1, maximum=52)
        if difficulty == "foundational":
            suggested_weeks = max(preferred, 6)
        elif difficulty == "advanced":
            suggested_weeks = min(preferred, 8)
        else:
            suggested_weeks = preferred

    return {
        "current_role_level": role_level,
        "target_role_level": target_seniority,
        "scope_difficulty": difficulty,
        "parse_confidence": parse_conf,
        "suggested_timeline_weeks": suggested_weeks,
        "capability_index": capability_index,
    }


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
                "ingestion_instructions": "Use documented API/file endpoint, land raw extract to bronze with run metadata, then apply conformance tests in silver before publishing gold KPIs.",
            }
        )
    return chosen


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
            "meta": {
                "provider": "scaffold",
                "model": "fallback",
                "base_url": base_url,
                "error_type": "provider",
                "reason_code": "LLM_API_KEY_MISSING",
            },
        }

    prompt_payload = {
        "candidate": {
            "name": intake.get("applicant_name"),
            "preferences": intake.get("preferences") or {},
            "resume_text": str(intake.get("resume_text") or "")[:4000],
            "self_assessment_text": str(intake.get("self_assessment_text") or "")[:4000],
        },
        "parsed_jobs": parsed_jobs[:8],
        "style_anchors": STYLE_ANCHORS,
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
            "data_source_shape": {"name": "string", "url": "https://real-link", "ingestion_doc_url": "https://real-doc-link", "ingestion_instructions": "explicit step-by-step instructions"},
            "milestone_shape": {
                "name": "string", "duration_weeks": "int>=1", "deliverables": ["string"],
                "execution_plan": "string", "expected_deliverable": "string", "business_why": "string",
                "milestone_tags": ["string"], "resources": [{"title": "string", "url": "https://real-link"}], "acceptance_checks": ["string"],
            },
            "project_story_required": ["executive_summary", "challenge", "approach", "impact_story"],
            "roi_required": ["required_dimensions", "required_measures"],
            "resources_required": ["required", "recommended", "optional", "affiliate_disclosure", "trust_language"],
            "project_charter_required": {
                "section_order": list(CHARTER_REQUIRED_SECTION_FLOW),
                "executive_summary_fields": ["current_state", "future_state"],
                "technical_architecture_requires": ["data_sources with url + ingestion_doc_url + ingestion_instructions"],
                "implementation_plan_requires": ["milestones with expectations + completion_criteria + acceptance checks"],
            },
            "hard_rules": [
                "Return JSON only, no markdown",
                "Mirror exemplar section sequence and flow exactly using top_level_order_required",
                "Keep content personalized to candidate resume/preferences/target roles (no generic placeholder narrative)",
                "Use realistic but fictitious business narrative with a named fictional company, business unit, and operating context",
                "Do not echo prompt instructions, rule labels, schema notes, or meta language (e.g., hard_rules, required_contract, return JSON only)",
                "Every story section must include concrete systems/process details and at least one measurable impact signal",
                "Use real non-placeholder URLs",
                "At least 3 milestones",
                "Each milestone must include execution_plan, expected_deliverable, and business_why",
                "Each milestone must include at least one resource link",
                "Each milestone must include at least two acceptance_checks",
                "Include at least one concrete public data source URL",
                "Include at least one ingestion documentation URL",
                "Each data source must include explicit ingestion_instructions",
                "Every data source must include ingestion_doc_url",
                "project_charter.section_order must match project_charter_required.section_order",
            ],
        },
    }

    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": "You are a senior data engineering consulting partner. Produce production-grade SOW JSON following the required contract exactly. Style-align to two anchors: GlobalMart Retail Intelligence Pipeline and VoltStream EV Grid Resilience. Match their executive charter tone, section depth, quantified KPI orientation, and implementation realism while keeping all details personalized and fictitious. Never output prompt/meta-instruction text. Invent a realistic fictitious company context and include concrete project depth: named systems, ingestion cadence, quality controls, artifact evidence, and measurable business outcomes. For each milestone, provide concrete execution details, measurable deliverable quality, explicit acceptance checks, and business rationale tied to outcomes.",
            },
            {"role": "user", "content": json.dumps(prompt_payload)},
        ],
        "response_format": {"type": "json_object"},
    }

    attempts = 0
    last_error = "unknown_error"
    error_type = "provider"
    reason_code = "LLM_PROVIDER_ERROR"
    while attempts <= max_retries:
        attempts += 1
        try:
            with httpx.Client(timeout=timeout) as client:
                resp = client.post(
                    f"{base_url}/chat/completions",
                    json=body,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                resp.raise_for_status()
                payload = resp.json()
            content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
            sow = _safe_json_loads(content)
            structure = evaluate_sow_structure(sow)
            if structure.get("missing_sections") or not structure.get("order_valid"):
                last_error = "LLM output failed required structure contract"
                error_type = "schema"
                reason_code = "LLM_SCHEMA_INVALID"
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
        except httpx.HTTPStatusError as e:
            status_code = int(e.response.status_code)
            last_error = f"HTTPError {status_code}"
            error_type = "provider"
            if status_code == 429:
                reason_code = "LLM_RATE_LIMITED"
            elif status_code in {401, 403}:
                reason_code = "LLM_AUTH_FAILED"
            elif status_code >= 500:
                reason_code = "LLM_UPSTREAM_5XX"
            else:
                reason_code = "LLM_HTTP_ERROR"
            if status_code < 500 and status_code not in {408, 429}:
                break
        except httpx.TimeoutException as e:
            last_error = str(e) or "timeout"
            error_type = "timeout"
            reason_code = "LLM_TIMEOUT"
        except httpx.RequestError as e:
            last_error = f"RequestError {e}"
            error_type = "network"
            reason_code = "LLM_NETWORK_ERROR"
        except json.JSONDecodeError as e:
            last_error = str(e)
            error_type = "schema"
            reason_code = "LLM_JSON_DECODE_ERROR"
            break
        except Exception as e:
            last_error = str(e)
            error_type = "provider"
            reason_code = "LLM_PROVIDER_ERROR"
        if attempts > max_retries:
            break

    return {
        "ok": False,
        "error": last_error,
        "sow": build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs),
        "meta": {
            "provider": "scaffold",
            "model": model,
            "base_url": base_url,
            "attempts": attempts,
            "error_type": error_type,
            "reason_code": reason_code,
        },
    }


def build_sow_skeleton(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
) -> dict[str, Any]:
    all_skills = sorted({s for p in parsed_jobs for s in p.get("signals", {}).get("skills", [])})
    all_tools = sorted({s for p in parsed_jobs for s in p.get("signals", {}).get("tools", [])})
    all_domains = sorted({s for p in parsed_jobs for s in p.get("signals", {}).get("domains", [])})

    project_title = f"{(intake.get('applicant_name') or 'Candidate')} - Northbeam Outfitters Omnichannel Margin Recovery Program"
    scope_profile = _derive_scope_profile(intake=intake, parsed_jobs=parsed_jobs)

    return {
        "schema_version": "0.2",
        "project_title": project_title,
        "candidate_profile": {
            "applicant_name": intake.get("applicant_name"),
            "preferences": intake.get("preferences") or {},
            "role_scope_assessment": scope_profile,
        },
        "business_outcome": {
            "problem_statement": "BlueOrbit Home Services cannot trust branch-level dispatch and upsell metrics because CRM events arrive 18-36 hours late and duplicate records slip into weekly leadership reporting.",
            "target_metrics": [
                {"metric": "pipeline_sla_minutes", "target": "<60"},
                {"metric": "dashboard_adoption_rate", "target": ">=60%"},
            ],
            "domain_focus": all_domains,
            "data_sources": _select_data_sources(intake=intake, parsed_jobs=parsed_jobs),
        },
        "solution_architecture": {
            "medallion_plan": {
                "bronze": "Land Salesforce Service Cloud events, branch dispatch CSV drops, and payroll extracts hourly to append-only bronze tables with ingestion timestamps, file hashes, and replay checkpoints.",
                "silver": "Standardize technician, branch, and work-order entities in dbt; enforce freshness/uniqueness tests; quarantine duplicates and schema-drift violations with alert routing to #data-ops.",
                "gold": "Publish executive KPI marts for first-visit resolution, technician utilization, and upsell conversion with semantic metric definitions versioned in Git and reconciled to finance totals.",
            },
            "primary_tools": all_tools,
            "target_skills": all_skills,
        },
        "project_story": {
            "executive_summary": "BlueOrbit Home Services will launch a medallion analytics program that unifies CRM, dispatch, and billing telemetry so operations leaders can trust branch KPIs in Monday reviews.",
            "challenge": "Current reports are manually reconciled across three systems, creating a 2-day lag and frequent metric disputes on technician utilization and first-visit resolution.",
            "approach": "Implement hourly bronze ingestion, silver conformance tests for key entities, and gold KPI marts with semantic definitions reviewed by operations and finance.",
            "impact_story": "Target outcomes include reducing report latency from 36 hours to under 90 minutes, lifting dashboard adoption above 70%, and cutting rework tied to bad dispatch data by 25%.",
        },
        "milestones": [
            {
                "name": "Discovery + Business framing",
                "duration_weeks": 1,
                "deliverables": ["scope brief", "KPI definitions"],
                "execution_plan": "Run a 90-minute discovery workshop with operations, finance, and branch managers; map Service Cloud objects, dispatch route files, and payroll extracts into a source-to-KPI matrix; then document KPI ownership and sign-off workflow in Confluence with explicit review dates.",
                "expected_deliverable": "Signed project charter with KPI dictionary, source inventory, and scope boundaries approved by sponsor.",
                "business_why": "Aligning scope and KPI definitions early prevents rework and accelerates measurable ROI delivery.",
                "milestone_tags": ["discovery", "architecture", "roi"],
                "resources": [{"title": "Kimball Dimensional Modeling", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"}],
                "acceptance_checks": ["Project charter signed by sponsor", "KPI dictionary validated in coach review"],
            },
            {
                "name": "Bronze/Silver implementation",
                "duration_weeks": 2,
                "deliverables": ["ingestion jobs", "DQ checks"],
                "execution_plan": "Implement hourly ingestion from API and flat-file sources into bronze with idempotent load keys, add schema-drift alerts in Airflow, and enforce silver dbt tests (freshness, uniqueness, accepted-values) before publishing daily quality scorecards.",
                "expected_deliverable": "Production-ready bronze/silver DAGs with tests, monitoring, and documented failure handling.",
                "business_why": "Reliable ingestion and conformance reduce reporting defects and improve trust in downstream analytics.",
                "milestone_tags": ["bronze", "silver", "pipeline"],
                "resources": [{"title": "Delta Lake Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"}],
                "acceptance_checks": ["Pipeline test suite passes in CI", "DQ threshold report validated and published"],
            },
            {
                "name": "Gold + ROI dashboard",
                "duration_weeks": 1,
                "deliverables": ["semantic model", "executive dashboard"],
                "execution_plan": "Build dimensional gold marts in dbt for technician, branch, and service-line performance; wire semantic metrics in Power BI with row-level security by region; and script reconciliation queries that compare dashboard totals to payroll and billing control reports before release.",
                "expected_deliverable": "Executive KPI dashboard package (PBIX + metric dictionary + SQL reconciliation workbook) with traceable source lineage and recorded stakeholder walkthrough.",
                "business_why": "Clear KPI visibility enables faster decisions and proves business impact of the data platform investment.",
                "milestone_tags": ["gold", "roi", "bi"],
                "resources": [{"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}],
                "acceptance_checks": ["Metric definitions validated against source tables", "Stakeholder review walkthrough recorded"],
            },
            {
                "name": "Final review + portfolio assets",
                "duration_weeks": 1,
                "deliverables": ["architecture narrative", "repo walkthrough"],
                "execution_plan": "Record a full stakeholder demo using production-like data, publish architecture decision records plus incident-response runbook in the repo, and deliver a retrospective quantifying KPI deltas, open risks, and next-quarter hardening backlog.",
                "expected_deliverable": "Release-tagged repository containing runbook, architecture diagram, automated test evidence, and a 10-minute narrated demo that ties KPI before/after math to signed stakeholder feedback.",
                "business_why": "Strong communication artifacts increase hiring signal and stakeholder confidence in project value.",
                "milestone_tags": ["communication", "career"],
                "resources": [{"title": "GitHub Portfolio Guide", "url": "https://docs.github.com/en/get-started/showcase-your-work/about-your-profile"}],
                "acceptance_checks": ["Demo script dry-run recorded with feedback", "Retrospective published with quantified outcomes"],
            },
        ],
        "roi_dashboard_requirements": {
            "required_dimensions": ["time", "business_unit", "product"],
            "required_measures": ["cost_savings", "revenue_impact", "sla_compliance"],
        },
        "resource_plan": {
            "required": [
                {"title": "Data Engineering Lifecycle Guide", "url": "https://martinfowler.com/articles/data-monolith-to-mesh.html"}
            ],
            "recommended": [],
            "optional": [],
            "affiliate_disclosure": "Some recommended resources may include affiliate links. Recommendations are selected for project relevance first.",
            "trust_language": "Resource recommendations are optional and do not change coaching feedback or project scoring.",
        },
        "mentoring_cta": {
            "recommended_tier": "starter" if scope_profile.get("scope_difficulty") == "foundational" else ("elite" if scope_profile.get("scope_difficulty") == "advanced" else "core"),
            "reason": f"Mapped from resume/job signals: current={scope_profile.get('current_role_level')} target={scope_profile.get('target_role_level')} scope={scope_profile.get('scope_difficulty')}.",
            "trust_language": "Mentoring recommendations are guidance-only and should align with the candidate's goals and budget.",
        },
        "project_charter": {
            "section_order": list(CHARTER_REQUIRED_SECTION_FLOW),
            "sections": {
                "prerequisites_resources": {
                    "summary": "Repository bootstrap, secure environment setup, and source-system access prerequisites tied to branch dispatch and CRM telemetry delivery.",
                    "resources": [
                        {"title": "GitHub Flow", "url": "https://docs.github.com/en/get-started/using-github/github-flow"},
                        {"title": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
                    ],
                },
                "executive_summary": {
                    "current_state": "Reporting is delayed and teams reconcile metrics manually.",
                    "future_state": "Decision makers use trusted self-serve KPIs refreshed on a predictable SLA.",
                },
                "technical_architecture": {
                    "platform": "Medallion architecture with orchestration, quality gates, and semantic layer.",
                    "data_sources": _select_data_sources(intake=intake, parsed_jobs=parsed_jobs, limit=2),
                },
                "implementation_plan": {
                    "milestones": [
                        {
                            "name": "Foundation + source onboarding",
                            "expectations": "Ingestion contracts, pipeline scaffolding, and CI checks merged.",
                            "completion_criteria": ["Source landed in bronze", "Automated tests green", "Runbook checked in"],
                        },
                        {
                            "name": "Modeling + KPI layer",
                            "expectations": "Silver/gold transformations with business metric definitions.",
                            "completion_criteria": ["Critical KPI SQL reviewed", "DQ thresholds enforced", "Stakeholder sign-off recorded"],
                        },
                    ],
                },
                "deliverables_acceptance_criteria": {
                    "deliverables": ["Architecture diagram", "Pipelines + tests", "Executive dashboard", "Demo narrative"],
                    "acceptance_criteria": ["Reproducible run evidence", "KPI definitions trace to source", "Business impact narrative is quantified"],
                },
                "risks_assumptions": {
                    "risks": ["Source schema drift", "Unclear KPI ownership", "Timeline compression due to stakeholder availability"],
                    "assumptions": ["Public source APIs remain available", "Candidate can dedicate weekly build cadence"],
                },
                "stretch_goals": {
                    "items": ["Add near-real-time ingestion path", "Implement semantic metric layer tests", "Publish interview walkthrough video"],
                },
            },
        },
        "interview_ready_package": _build_interview_ready_package(
            project_title=project_title,
            story={
                "challenge": "Operations teams spent two days reconciling CRM, dispatch, and billing exports before every weekly executive review.",
                "approach": "Built hourly ingestion + conformance checks, then published KPI marts with metric contracts owned by operations and finance.",
                "impact_story": "Cut reporting latency below 90 minutes and reduced dispatch-data correction workload by 25% in pilot branches.",
            },
            milestones=[],
            tools=all_tools,
        ),
    }
