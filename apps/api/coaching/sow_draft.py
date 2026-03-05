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
                "Use realistic but fictitious business narrative",
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
                "content": "You are a senior data engineering consulting partner. Produce production-grade SOW JSON following the required contract exactly. Style-align to two anchors: GlobalMart Retail Intelligence Pipeline and VoltStream EV Grid Resilience. Match their executive charter tone, section depth, quantified KPI orientation, and implementation realism while keeping all details personalized and fictitious. For each milestone, provide concrete execution details, measurable deliverable quality, explicit acceptance checks, and business rationale tied to outcomes.",
            },
            {"role": "user", "content": json.dumps(prompt_payload)},
        ],
        "response_format": {"type": "json_object"},
    }

    attempts = 0
    last_error = "unknown_error"
    error_type = "provider"
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
            last_error = f"HTTPError {e.response.status_code}"
            error_type = "provider"
            if e.response.status_code < 500 and e.response.status_code not in {408, 429}:
                break
        except httpx.TimeoutException as e:
            last_error = str(e) or "timeout"
            error_type = "timeout"
        except httpx.RequestError as e:
            last_error = f"RequestError {e}"
            error_type = "network"
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
            "model": model,
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
                "acceptance_checks": ["Charter signed by sponsor", "KPI dictionary reviewed with coach"],
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
                "acceptance_checks": ["Pipeline test suite passes in CI", "DQ threshold report attached"],
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
                "acceptance_checks": ["Metric definitions traced to source tables", "Stakeholder review walkthrough recorded"],
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
                "acceptance_checks": ["Demo script dry-run completed", "Retrospective includes quantified outcomes"],
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
        "project_charter": {
            "section_order": list(CHARTER_REQUIRED_SECTION_FLOW),
            "sections": {
                "prerequisites_resources": {
                    "summary": "Repo scaffold, environment setup, and source access prerequisites.",
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
                "challenge": "Translate fragmented source data into trusted KPI reporting under tight delivery timelines.",
                "approach": "Implement bronze/silver/gold pipelines, data quality checks, and executive-friendly ROI dashboards.",
                "impact_story": "Demonstrate end-to-end ownership from ingestion through business narrative and stakeholder-ready metrics.",
            },
            milestones=[],
            tools=all_tools,
        ),
    }
