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
from .sow_validation import (
    evaluate_sow_structure,
    _build_interview_ready_package,
    validate_sow_payload,
    compute_sow_quality_score,
    normalize_generated_sow,
)


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
    resume_summary = ((intake.get("preferences") or {}).get("resume_parse_summary") or {}) if isinstance((intake.get("preferences") or {}), dict) else {}
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
    for bucket in ["tools", "domains", "project_experience_keywords"]:
        for term in (resume_summary.get(bucket) or []):
            if str(term).strip():
                preference_terms.add(str(term).strip().lower())
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


def _candidate_source_by_name(name: str) -> dict[str, str]:
    for candidate in DATA_SOURCE_CANDIDATES:
        if str(candidate.get("name") or "") == name:
            return {
                "name": str(candidate.get("name") or ""),
                "url": str(candidate.get("url") or ""),
                "ingestion_doc_url": str(candidate.get("ingestion_doc_url") or ""),
                "selection_rationale": str(candidate.get("selection_rationale") or "Selected for relevance to target project outcomes."),
                "ingestion_instructions": "Use documented API/file endpoint, land raw extract to bronze with run metadata, then apply conformance tests in silver before publishing gold KPIs.",
            }
    return {}


def _ensure_data_sources(selected_sources: list[dict[str, str]], preferred_names: list[str], limit: int = 3) -> list[dict[str, str]]:
    ordered: list[dict[str, str]] = []
    seen_names: set[str] = set()
    for name in preferred_names:
        source = _candidate_source_by_name(name)
        source_name = str(source.get("name") or "")
        if source_name and source_name not in seen_names:
            ordered.append(source)
            seen_names.add(source_name)
    for source in selected_sources:
        source_name = str(source.get("name") or "")
        if source_name and source_name not in seen_names:
            ordered.append(source)
            seen_names.add(source_name)
    return ordered[: max(1, int(limit))]


def _preferred_serving_tool(all_tools: list[str]) -> str:
    tools = {str(tool).strip().lower() for tool in (all_tools or []) if str(tool).strip()}
    if "tableau" in tools and "power bi" not in tools:
        return "Tableau"
    return "Power BI"


def _infer_project_archetype(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
    all_domains: list[str],
    all_tools: list[str],
) -> str:
    resume_summary = ((intake.get("preferences") or {}).get("resume_parse_summary") or {}) if isinstance((intake.get("preferences") or {}), dict) else {}
    keywords = {
        str(term).strip().lower()
        for term in (
            (resume_summary.get("project_experience_keywords") or [])
            + (resume_summary.get("domains") or [])
            + (resume_summary.get("tools") or [])
            + all_domains
            + all_tools
        )
        if str(term).strip()
    }
    for job in parsed_jobs or []:
        signals = job.get("signals") or {}
        for bucket in ["skills", "tools", "domains"]:
            for term in (signals.get(bucket) or []):
                if str(term).strip():
                    keywords.add(str(term).strip().lower())

    retail_terms = {"retail", "ecommerce", "omnichannel", "inventory", "merchandising", "sales", "customer", "margin", "pricing", "basket", "store"}
    energy_terms = {"energy", "utilities", "ev", "charging", "grid", "outage", "weather", "resilience", "power", "forecast", "load", "telemetry"}
    finance_terms = {"finance", "crypto", "donation", "donations", "market", "liquidation", "latency", "realtime", "real-time", "trading", "coingecko", "volatility"}

    retail_score = len(keywords & retail_terms)
    energy_score = len(keywords & energy_terms)
    finance_score = len(keywords & finance_terms)
    if finance_score >= max(retail_score, energy_score) and finance_score >= 1:
        return "finance"
    if energy_score > retail_score and energy_score >= 1:
        return "energy"
    if retail_score >= 1:
        return "retail"
    return "general"


def _build_common_resource_plan(serving_tool: str) -> dict[str, Any]:
    serving_guidance_url = "https://help.tableau.com/current/guides/en-us/guidance.htm" if serving_tool == "Tableau" else "https://learn.microsoft.com/en-us/power-bi/guidance/"
    serving_guidance_title = "Tableau Blueprint" if serving_tool == "Tableau" else "Power BI Design Guidance"
    return {
        "required": [
            {"title": "Databricks Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"},
            {"title": serving_guidance_title, "url": serving_guidance_url},
        ],
        "recommended": [
            {"title": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
            {"title": "Kimball Group", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"},
        ],
        "optional": [
            {"title": "Storytelling with Data", "url": "https://www.storytellingwithdata.com/"},
        ],
        "affiliate_disclosure": "Some recommended resources may include affiliate links. Recommendations are selected for project relevance first.",
        "trust_language": "Resource recommendations are optional and do not change coaching feedback or project scoring.",
    }


def _build_retail_archetype(
    intake: dict[str, Any],
    all_skills: list[str],
    all_tools: list[str],
    selected_sources: list[dict[str, str]],
    serving_tool: str,
) -> dict[str, Any]:
    project_title = f"{(intake.get('applicant_name') or 'Candidate')} - GlobalMart Retail Intelligence Pipeline"
    serving_connection = "validated Tableau extracts and published workbooks with governed metric definitions" if serving_tool == "Tableau" else "gold marts and published Power BI semantic models with governed metric definitions"
    dashboard_resource = {"title": "Tableau Blueprint", "url": "https://help.tableau.com/current/guides/en-us/guidance.htm"} if serving_tool == "Tableau" else {"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}
    milestones = [
        {
            "name": "Current-state retail discovery",
            "duration_weeks": 1,
            "deliverables": ["project charter", "source-to-KPI matrix", "stakeholder map"],
            "execution_plan": "Interview merchandising, e-commerce, and supply chain stakeholders; map order, inventory, and returns source fields to executive retail KPIs; then document refresh cadence, ownership, and report pain points in a charter packet that mirrors an internal consulting kickoff.",
            "expected_deliverable": "Signed charter with current-state pain points, future-state KPI plan, and a source inventory covering sales, inventory, and return workflows.",
            "business_why": "The project must ground technical design in a believable merchandising and margin problem, not generic reporting language.",
            "milestone_tags": ["discovery", "architecture", "roi"],
            "resources": [{"title": "Kimball Dimensional Modeling", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"}],
            "acceptance_checks": ["Project charter signed and KPI matrix approved by sponsor", "KPI matrix published with source owner, refresh SLA, and sign-off date"],
        },
        {
            "name": "Retail bronze and silver foundation",
            "duration_weeks": 2,
            "deliverables": ["bronze ingestion notebooks", "silver conformance tests", "entity model"],
            "execution_plan": "Land order, product, and inventory extracts into bronze with batch metadata, deduplicate transaction records, and standardize store, SKU, and date dimensions in silver using SQL/dbt quality tests before promoting any margin or stockout metrics.",
            "expected_deliverable": "Reproducible bronze-to-silver pipeline with documented schema checks, late-arriving record handling, and a conformed retail entity model.",
            "business_why": "Retail decisions break down when returns, promotions, or inventory snapshots are not modeled consistently across channels.",
            "milestone_tags": ["bronze", "silver", "pipeline"],
            "resources": [{"title": "Delta Lake Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"}],
            "acceptance_checks": ["Silver tests pass for null keys, duplicates, and stale loads", "Order and inventory grain validated in architecture review notes"],
        },
        {
            "name": "Executive retail KPI mart",
            "duration_weeks": 1,
            "deliverables": ["gold mart", "executive dashboard", "metric dictionary"],
            "execution_plan": f"Build gold marts for sales, gross margin, inventory turns, and return rate by store and channel; publish the executive dashboard in {serving_tool}; and reconcile KPI totals back to source extracts before recording the stakeholder walkthrough.",
            "expected_deliverable": f"{serving_tool} dashboard package with a metric dictionary, lineage notes, and business-ready views for margin, inventory, and returns analysis.",
            "business_why": "Executives need one trusted place to answer why margin is moving across stores, products, and channels.",
            "milestone_tags": ["gold", "roi", "bi"],
            "resources": [dashboard_resource],
            "acceptance_checks": ["Gross margin KPI validated against source sales totals", "Dashboard walkthrough recorded and published with sponsor feedback"],
        },
        {
            "name": "Portfolio packaging and hiring narrative",
            "duration_weeks": 1,
            "deliverables": ["demo walkthrough", "architecture diagram", "resume bullets"],
            "execution_plan": "Package the project like a client delivery: publish the architecture diagram in the GitHub repo, document retail modeling choices in the README, record a 10-minute narrated dashboard demo, and distill the work into interview-ready bullets tied to gross-margin and inventory-turn outcomes.",
            "expected_deliverable": "Release-tagged portfolio package with repo, runbook, architecture diagram, recorded demo link, and a concise interview story that references measured KPI outcomes.",
            "business_why": "A premium project should be easy to explain to recruiters, hiring managers, and technical interviewers.",
            "milestone_tags": ["communication", "career"],
            "resources": [{"title": "GitHub Portfolio Guide", "url": "https://docs.github.com/en/get-started/showcase-your-work/about-your-profile"}],
            "acceptance_checks": ["Demo walkthrough recorded and published in the repository", "Resume bullets validated against repo artifacts and measured KPI outcomes"],
        },
    ]
    return {
        "project_title": project_title,
        "business_outcome": {
            "problem_statement": "GlobalMart leadership lacks a trusted cross-channel view of margin, inventory turns, and return behavior because store, e-commerce, and product extracts refresh on different cadences and break KPI consistency during Monday business reviews.",
            "current_state": "Merchandising and finance teams reconcile sales, inventory, and returns in spreadsheets, delaying root-cause analysis for stockouts, markdown pressure, and margin erosion.",
            "future_state": "A retail intelligence lakehouse publishes decision-grade gold KPIs by store, channel, and product family with explicit lineage from bronze ingestion through silver conformance and executive-ready dashboard views.",
            "target_metrics": [
                {"metric": "margin_report_latency_hours", "target": "<4"},
                {"metric": "inventory_turn_visibility", "target": "daily by store and channel"},
                {"metric": "manual_reconciliation_reduction", "target": ">=30%"},
            ],
            "domain_focus": ["retail", "ecommerce"],
            "data_sources": selected_sources,
        },
        "solution_architecture": {
            "ingestion": {
                "source_pattern": "Daily retail flat-file loads plus documented public extracts for orders, products, and inventory snapshots.",
                "cadence": "Daily for core sales and inventory facts, weekly for macro context enrichments.",
            },
            "processing": {
                "engine": "PySpark plus SQL/dbt transformations",
                "orchestration": "Scheduled workflows with freshness alerts, duplicate detection, and late-arriving dimension handling.",
            },
            "storage": {
                "bronze": "Raw order, product, and inventory payloads with batch metadata and source load timestamps.",
                "silver": "Conformed retail entities for orders, stores, products, returns, and calendar dimensions.",
                "gold": "Executive marts for margin, inventory turns, sell-through, stockout risk, and return rate trends.",
            },
            "serving": {
                "tool": serving_tool,
                "connection": serving_connection,
            },
            "medallion_plan": {
                "bronze": "Ingest retail sales and inventory files with reproducible batch IDs, source filenames, and row-count checks so every run can be replayed and audited.",
                "silver": "Conform store, product, and transaction grains; standardize returns logic; and enforce freshness, uniqueness, and accepted-values checks before KPI aggregation.",
                "gold": "Publish executive-ready marts for gross margin, return rate, inventory turns, and channel performance with documented calculation logic and retailer-facing business labels.",
            },
            "primary_tools": all_tools,
            "target_skills": all_skills,
        },
        "project_story": {
            "executive_summary": "GlobalMart Retail Intelligence Pipeline gives merchandising leaders a trustworthy gross-margin KPI view by unifying POS, e-commerce, and inventory datasets into a bronze, silver, and gold retail stack that refreshes within 4 hours for Monday business reviews.",
            "challenge": "Leadership currently sees conflicting POS and e-commerce numbers, cannot explain why selected product categories lose 3% to 5% of margin after returns and markdowns, and loses hours each week validating stockout and markdown narratives before business reviews.",
            "approach": f"Implement a bronze-to-gold retail pipeline, enforce conformed product and store dimensions, reconcile gross-margin KPI logic in SQL/dbt, and publish a {serving_tool} executive dashboard backed by documented gold marts and a formal metric dictionary.",
            "impact_story": "The project targets a 30% reduction in spreadsheet reconciliation, daily visibility into inventory-turn KPI trends, and a measurable reduction in report latency from multi-day prep to a 4-hour dashboard SLA.",
        },
        "milestones": milestones,
        "roi_dashboard_requirements": {
            "required_dimensions": ["date", "store", "channel", "product_category", "region"],
            "required_measures": ["gross_sales", "gross_margin", "return_rate", "inventory_turns", "stockout_risk"],
            "business_questions": [
                "Which stores or channels are driving the largest margin compression this week?",
                "Where are inventory turns slowing down enough to increase stockout or markdown risk?",
                "Which product categories have elevated return rates that undermine gross margin performance?",
            ],
            "visual_requirements": [
                "Include an executive KPI band for gross sales, gross margin, and return rate.",
                "Show a trend comparing channel performance over time with store drill-down.",
                "Highlight the worst-performing categories or regions with clear annotation for business leaders.",
            ],
            "primary_kpi": "Gross Margin",
        },
        "project_charter_sections": {
            "prerequisites_resources": {
                "summary": "Before kickoff, confirm the retail dataset mix, source field meanings, and the candidate's readiness to model order, inventory, and return facts at the correct grain.",
                "data_assets": [
                    {
                        "name": "Retail sales and inventory source set",
                        "url": (selected_sources[0].get("url") if selected_sources else ""),
                        "ingestion_doc_url": (selected_sources[0].get("ingestion_doc_url") if selected_sources else ""),
                        "action": "Review source fields, document transaction grain, and define how orders, products, and inventory snapshots land in bronze before modeling begins.",
                    }
                ],
                "tools": [
                    {"name": "GitHub", "url": "https://docs.github.com/en/get-started/using-github/github-flow"},
                    {"name": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
                    {"name": serving_tool, "url": dashboard_resource["url"]},
                ],
                "skill_check": "The candidate should be comfortable explaining fact/dimension grain, writing SQL joins, and defending KPI definitions such as gross margin, return rate, and inventory turns.",
                "resources": [
                    {"title": "Kimball Group", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"},
                    {"title": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
                ],
            },
            "executive_summary": {
                "current_state": "Retail leaders work from mismatched channel reports, limited inventory context, and manual spreadsheet reconciliation before each business review.",
                "future_state": "Leaders consume trusted store and channel KPIs from a governed gold layer with clear lineage, definitions, and daily refresh expectations.",
            },
            "technical_architecture": {
                "platform": "Retail lakehouse using medallion architecture, orchestration, and BI semantic modeling.",
                "ingestion": {
                    "source": "Retail sales, product, and inventory extracts plus optional macro or labor context datasets.",
                    "pattern": "Replay-safe bronze loads with batch metadata, source row counts, and explicit refresh cadence.",
                },
                "processing": {
                    "engine": "PySpark plus SQL/dbt transformations",
                    "logic": "Conformed order, product, store, and inventory entities with KPI quality checks and documented business logic.",
                },
                "storage": {
                    "bronze": "Raw sales, inventory, and returns extracts with source traceability.",
                    "silver": "Conformed retail entities with quality enforcement and grain documentation.",
                    "gold": "Retail KPI marts for margin, turns, sell-through, stockout risk, and return analysis.",
                },
                "serving": {
                    "tool": serving_tool,
                    "connection": serving_connection,
                },
                "data_sources": selected_sources[:2],
            },
            "implementation_plan": {
                "milestones": [
                    {
                        "name": "Retail source profiling and KPI framing",
                        "expectations": "Source inventory, grain documentation, and sponsor-approved KPI definitions are checked in.",
                        "completion_criteria": ["Source-to-KPI matrix completed", "Current-state pain points documented", "Project charter approved"],
                        "estimated_effort_hours": 4,
                        "key_concept": "Retail KPI framing",
                    },
                    {
                        "name": "Order and inventory conformance",
                        "expectations": "Core retail facts and dimensions are standardized with automated quality rules.",
                        "completion_criteria": ["Silver tests are green", "Inventory and returns logic documented", "Late-arriving records handled"],
                        "estimated_effort_hours": 6,
                        "key_concept": "Conformed retail modeling",
                    },
                    {
                        "name": "Executive dashboard and portfolio handoff",
                        "expectations": "Gold KPI marts support real business questions and are packaged into an interview-ready portfolio narrative.",
                        "completion_criteria": ["Dashboard walkthrough recorded", "Metric dictionary reconciles to source", "Portfolio artifacts published"],
                        "estimated_effort_hours": 5,
                        "key_concept": "Decision-grade storytelling",
                    },
                ],
            },
            "deliverables_acceptance_criteria": {
                "deliverables": ["Architecture diagram", "Retail bronze/silver/gold pipeline", "Executive dashboard", "Narrated project walkthrough"],
                "acceptance_criteria": ["Order and inventory grain are documented", "Gross margin KPI reconciles to source data", "Business outcomes are quantified in the walkthrough"],
            },
            "risks_assumptions": {
                "risks": ["Retail extracts may not include stable SKU keys", "Return logic can distort margin if modeled inconsistently", "Stakeholder KPI definitions may shift mid-project"],
                "assumptions": ["Selected public data sources remain accessible", "Candidate can sustain a weekly delivery cadence and review feedback quickly"],
            },
            "stretch_goals": {
                "items": ["Add promotional markdown analysis", "Publish semantic layer tests for margin KPIs", "Create a short case-study PDF for recruiters"],
            },
        },
        "interview_story": {
            "challenge": "Merchandising and finance teams were spending too much time reconciling cross-channel sales, inventory, and returns before leadership reviews.",
            "approach": f"Built a retail bronze-to-gold pipeline with conformed product and store dimensions, then surfaced reconciled KPI marts in {serving_tool}.",
            "impact_story": "Created a decision-grade retail analytics story with clearer margin visibility, lower reconciliation effort, and a credible portfolio narrative.",
        },
    }


def _build_energy_archetype(
    intake: dict[str, Any],
    all_skills: list[str],
    all_tools: list[str],
    selected_sources: list[dict[str, str]],
    serving_tool: str,
) -> dict[str, Any]:
    project_title = f"{(intake.get('applicant_name') or 'Candidate')} - Project VoltStream Grid Resilience Charter"
    serving_connection = "validated Tableau extracts and operational workbooks with governed metric definitions" if serving_tool == "Tableau" else "gold marts and published Power BI semantic models with governed resilience metrics"
    dashboard_resource = {"title": "Tableau Blueprint", "url": "https://help.tableau.com/current/guides/en-us/guidance.htm"} if serving_tool == "Tableau" else {"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}
    milestones = [
        {
            "name": "Grid resilience framing and source alignment",
            "duration_weeks": 1,
            "deliverables": ["charter packet", "risk model outline", "source access notes"],
            "execution_plan": "Document the current-state EV charging and weather telemetry problem, align outage-risk and utilization questions with sponsor goals, capture Open Charge Map and OpenWeather API request patterns, and publish a source access plan that shows how raw JSON lands in bronze tables with hourly cadence and evidence queries.",
            "expected_deliverable": "Approved charter packet with current-state blind spots, future-state resilience visibility, API source inventory, and published bronze-ingestion evidence for the telemetry feeds required to support the project.",
            "business_why": "A believable energy project needs concrete operational risk framing before any technical build work begins.",
            "milestone_tags": ["discovery", "architecture", "roi"],
            "resources": [{"title": "Open Charge Map API", "url": "https://openchargemap.org/site/develop/api"}],
            "acceptance_checks": ["Risk narrative approved by sponsor and tied to charging operations", "Source onboarding notes published with cadence and ingestion method"],
        },
        {
            "name": "Telemetry ingestion and silver risk modeling",
            "duration_weeks": 2,
            "deliverables": ["bronze landing jobs", "silver standardized tables", "quality scorecards"],
            "execution_plan": "Ingest charger location and status telemetry alongside weather features, flatten nested JSON into bronze, standardize site, connector, and region entities in silver, and implement data quality checks for stale telemetry and null geo fields.",
            "expected_deliverable": "Operational bronze/silver pipeline with telemetry normalization, weather enrichment, and documented quality thresholds.",
            "business_why": "Grid resilience analysis fails if charger status, geography, and weather context are not joined and validated consistently.",
            "milestone_tags": ["bronze", "silver", "pipeline"],
            "resources": [{"title": "OpenWeather One Call API", "url": "https://openweathermap.org/api/one-call-3"}],
            "acceptance_checks": ["Telemetry freshness checks pass for the hourly ingestion window", "Region and connector joins validated in reproducible notebook evidence"],
        },
        {
            "name": "Resilience dashboard and operating narrative",
            "duration_weeks": 1,
            "deliverables": ["gold marts", "risk dashboard", "metric contract"],
            "execution_plan": f"Publish gold marts for charger utilization, outage exposure, weather-linked risk, and regional coverage; then surface them in {serving_tool} with executive annotations that explain where resilience risk is concentrated and why.",
            "expected_deliverable": f"{serving_tool} resilience dashboard package with risk scoring logic, metric definitions, and supporting SQL or notebook evidence.",
            "business_why": "Leadership needs to know which regions or sites require intervention before uptime and customer experience erode.",
            "milestone_tags": ["gold", "roi", "bi"],
            "resources": [dashboard_resource],
            "acceptance_checks": ["Risk scores validated against source weather and charger telemetry", "Dashboard walkthrough recorded and published with sponsor outage questions"],
        },
        {
            "name": "Executive closeout and interview-ready package",
            "duration_weeks": 1,
            "deliverables": ["stakeholder demo", "architecture brief", "portfolio summary"],
            "execution_plan": "Record a short executive walkthrough, publish the architecture and risk-model narrative, and turn the project into a portfolio asset that emphasizes operational realism, public API ingestion, and measurable resilience outcomes.",
            "expected_deliverable": "Portfolio-ready package with repo, published architecture notes, recorded executive walkthrough, and an interview script tied to measured outage-exposure KPI outcomes.",
            "business_why": "A strong project should translate operational energy telemetry work into a concise hiring narrative.",
            "milestone_tags": ["communication", "career"],
            "resources": [{"title": "GitHub Portfolio Guide", "url": "https://docs.github.com/en/get-started/showcase-your-work/about-your-profile"}],
            "acceptance_checks": ["Demo walkthrough recorded and published with operational risk commentary", "Repository evidence validated to include runbook, quality checks, and dashboard outputs"],
        },
    ]
    return {
        "project_title": project_title,
        "business_outcome": {
            "problem_statement": "VoltStream operations cannot see which charging regions face the highest outage exposure because charger telemetry, location metadata, and weather context live in disconnected feeds with inconsistent refresh and no decision-grade resilience KPI layer.",
            "current_state": "Operations teams react to charger downtime and weather disruptions after the fact, using ad hoc exports and maps that do not combine utilization, outage, and weather signals in one place.",
            "future_state": "A resilience-focused lakehouse combines charging infrastructure telemetry, weather context, and regional demand signals into governed gold KPIs that support proactive operational decisions.",
            "target_metrics": [
                {"metric": "telemetry_freshness_minutes", "target": "<30"},
                {"metric": "regional_risk_visibility", "target": "daily across all priority regions"},
                {"metric": "manual_incident_triage_reduction", "target": ">=25%"},
            ],
            "domain_focus": ["energy", "ev", "operations"],
            "data_sources": selected_sources,
        },
        "solution_architecture": {
            "ingestion": {
                "source_pattern": "API-first bronze ingestion for charger telemetry and weather context with region-level enrichment tables.",
                "cadence": "Hourly for charging telemetry and weather features, daily for supporting demand context.",
            },
            "processing": {
                "engine": "PySpark plus SQL/dbt transformations",
                "orchestration": "Scheduled workflows with API retry handling, freshness monitoring, and anomaly alerts for stale regional feeds.",
            },
            "storage": {
                "bronze": "Raw charging and weather API payloads with load metadata, request windows, and retry context.",
                "silver": "Standardized site, connector, geography, weather, and telemetry entities with quality enforcement.",
                "gold": "Regional resilience marts for outage exposure, utilization, site health, and weather-linked risk scoring.",
            },
            "serving": {
                "tool": serving_tool,
                "connection": serving_connection,
            },
            "medallion_plan": {
                "bronze": "Pull charger point and weather feeds on a repeatable cadence, persist raw JSON with request parameters, and track freshness to support replay and troubleshooting.",
                "silver": "Normalize sites, connectors, and weather attributes; handle nested API structures; and enforce quality checks for null geographies, stale telemetry, and malformed status codes.",
                "gold": "Publish resilience marts that quantify utilization, outage exposure, weather risk, and regional service coverage with explicit metric definitions for executive use.",
            },
            "primary_tools": all_tools,
            "target_skills": all_skills,
        },
        "project_story": {
            "executive_summary": "Project VoltStream turns public charging and weather APIs into a resilience KPI layer by landing hourly telemetry in bronze, standardizing site health in silver, and publishing gold outage-exposure dashboards for grid operations leaders.",
            "challenge": "Site operators cannot predict which regions face the highest utilization or outage risk because charger status, geography, and weather conditions live in separate APIs, leading to 30-minute to multi-hour blind spots during regional disruption events.",
            "approach": f"Build an API-first medallion pipeline, standardize charging and weather entities, validate telemetry freshness every hour, and publish a {serving_tool} resilience dashboard that links operational risk to measurable uptime and outage metrics.",
            "impact_story": "The project aims to reduce manual telemetry triage by 25%, improve regional risk visibility each hour, and give operations leaders a measurable outage-exposure KPI backed by source evidence.",
        },
        "milestones": milestones,
        "roi_dashboard_requirements": {
            "required_dimensions": ["date_hour", "region", "site", "connector_type", "weather_condition"],
            "required_measures": ["charger_utilization", "outage_exposure", "telemetry_freshness", "weather_risk_score", "site_health_index"],
            "business_questions": [
                "Which regions have the highest concentration of charger outage risk right now?",
                "How does severe weather correlate with utilization drops or outage exposure by region?",
                "Which sites should operations prioritize because they combine high demand with fragile service coverage?",
            ],
            "visual_requirements": [
                "Include an executive KPI band for utilization, outage exposure, and telemetry freshness.",
                "Show a regional trend or map view that connects weather events to resilience risk.",
                "Highlight the sites or regions requiring immediate operational attention with business-readable labels.",
            ],
            "primary_kpi": "Outage Exposure",
        },
        "project_charter_sections": {
            "prerequisites_resources": {
                "summary": "Before kickoff, confirm API access assumptions, document charger and weather field meanings, and verify the candidate can explain telemetry ingestion, dimensional joins, and resilience KPI definitions.",
                "data_assets": [
                    {
                        "name": "Charging and weather telemetry set",
                        "url": (selected_sources[0].get("url") if selected_sources else ""),
                        "ingestion_doc_url": (selected_sources[0].get("ingestion_doc_url") if selected_sources else ""),
                        "action": "Review the charger and weather API documentation, define cadence and request windows, and document how raw JSON is persisted to bronze before modeling begins.",
                    }
                ],
                "tools": [
                    {"name": "GitHub", "url": "https://docs.github.com/en/get-started/using-github/github-flow"},
                    {"name": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
                    {"name": serving_tool, "url": dashboard_resource["url"]},
                ],
                "skill_check": "The candidate should be comfortable with JSON ingestion, SQL joins across site and geography dimensions, and explaining why telemetry freshness matters to operational decisions.",
                "resources": [
                    {"title": "Open Charge Map API", "url": "https://openchargemap.org/site/develop/api"},
                    {"title": "OpenWeather One Call API", "url": "https://openweathermap.org/api/one-call-3"},
                ],
            },
            "executive_summary": {
                "current_state": "Operations teams lack a unified view of charging site health, weather-linked disruption risk, and regional coverage pressure.",
                "future_state": "Leaders use governed resilience KPIs to prioritize interventions before utilization and uptime degrade across critical regions.",
            },
            "technical_architecture": {
                "platform": "API-first energy telemetry lakehouse with medallion architecture, quality controls, and operational BI serving.",
                "ingestion": {
                    "source": "Charging infrastructure APIs, weather APIs, and optional region-level demand context feeds.",
                    "pattern": "Replay-safe bronze JSON ingestion with request metadata, freshness tracking, and retry-safe orchestration.",
                },
                "processing": {
                    "engine": "PySpark plus SQL/dbt transformations",
                    "logic": "Standardize site, connector, region, and weather entities while enforcing freshness, null-check, and anomaly detection rules.",
                },
                "storage": {
                    "bronze": "Raw API payloads with request traces and response metadata.",
                    "silver": "Conformed telemetry, geography, and weather entities with quality enforcement.",
                    "gold": "Operational marts for utilization, outage exposure, site health, and resilience scoring.",
                },
                "serving": {
                    "tool": serving_tool,
                    "connection": serving_connection,
                },
                "data_sources": selected_sources[:2],
            },
            "implementation_plan": {
                "milestones": [
                    {
                        "name": "Telemetry onboarding and resilience framing",
                        "expectations": "APIs, request windows, and sponsor business questions are documented in the charter.",
                        "completion_criteria": ["API cadence defined", "Current and future state approved", "Source access notes checked in"],
                        "estimated_effort_hours": 4,
                        "key_concept": "Operational telemetry framing",
                    },
                    {
                        "name": "Standardization and quality controls",
                        "expectations": "Telemetry, weather, and region entities are conformed with freshness and anomaly checks.",
                        "completion_criteria": ["Silver quality checks pass", "Risk model inputs are documented", "Freshness monitoring is visible"],
                        "estimated_effort_hours": 6,
                        "key_concept": "Telemetry conformance",
                    },
                    {
                        "name": "Resilience KPI delivery and narrative",
                        "expectations": "Gold marts answer sponsor risk questions and are packaged into a portfolio-quality walkthrough.",
                        "completion_criteria": ["Dashboard walkthrough recorded", "Risk scores reconcile to source data", "Portfolio summary published"],
                        "estimated_effort_hours": 5,
                        "key_concept": "Operational risk storytelling",
                    },
                ],
            },
            "deliverables_acceptance_criteria": {
                "deliverables": ["Architecture diagram", "Telemetry bronze/silver/gold pipeline", "Resilience dashboard", "Narrated project walkthrough"],
                "acceptance_criteria": ["Telemetry freshness is measurable", "Risk metrics trace to source APIs", "Business actions are clear in the walkthrough"],
            },
            "risks_assumptions": {
                "risks": ["Public API rate limits may affect cadence", "Weather enrichment windows may need tuning", "Telemetry quality may vary by region or site"],
                "assumptions": ["Selected APIs remain available", "Candidate can explain operational energy metrics in plain business language"],
            },
            "stretch_goals": {
                "items": ["Add alerting logic for high-risk regions", "Publish a simple site-health semantic layer", "Create a recruiter-facing one-page case study"],
            },
        },
        "interview_story": {
            "challenge": "Operations leaders could not combine charging telemetry and weather context quickly enough to manage resilience risk.",
            "approach": f"Built an API-first bronze-to-gold pipeline for charger and weather telemetry, then surfaced resilience KPIs in {serving_tool}.",
            "impact_story": "Created a realistic operations analytics story with clearer regional risk visibility and a portfolio-ready data engineering narrative.",
        },
    }


def _build_finance_archetype(
    intake: dict[str, Any],
    all_skills: list[str],
    all_tools: list[str],
    selected_sources: list[dict[str, str]],
    serving_tool: str,
) -> dict[str, Any]:
    project_title = f"{(intake.get('applicant_name') or 'Candidate')} - Global Giving Network Market & Donation Velocity Monitor"
    serving_connection = "validated Tableau extracts and live alert workbooks with governed metric definitions" if serving_tool == "Tableau" else "gold Delta marts and published Power BI semantic models with latency and alert metrics"
    dashboard_resource = {"title": "Tableau Blueprint", "url": "https://help.tableau.com/current/guides/en-us/guidance.htm"} if serving_tool == "Tableau" else {"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}
    milestones = [
        {
            "name": "Live API connectivity and retry logic",
            "duration_weeks": 1,
            "deliverables": ["Databricks notebook", "API connectivity evidence", "retry strategy"],
            "execution_plan": "Build a Databricks notebook that calls CoinGecko /simple/price and /coins/markets with Python requests, logs response time and status code, and implements a 5-second retry path so failed API calls can be replayed before bronze ingestion begins.",
            "expected_deliverable": "Published notebook with live CoinGecko payload examples, 200-status evidence, retry logic, and request-latency notes for the donation-monitor pipeline.",
            "business_why": "The nonprofit team cannot trigger high-value liquidation alerts without trusted near real-time market signals and measurable API latency evidence.",
            "milestone_tags": ["discovery", "architecture", "roi"],
            "resources": [{"title": "CoinGecko Simple Price API Reference", "url": "https://docs.coingecko.com/v3.0.1/reference/simple-price"}],
            "acceptance_checks": ["Live CoinGecko payload recorded with a 200 status code", "Retry logic validated with a simulated failed request and published notebook output"],
        },
        {
            "name": "Bronze landing and Delta persistence",
            "duration_weeks": 1,
            "deliverables": ["bronze Delta table", "append-mode ingestion job", "row-count audit"],
            "execution_plan": "Convert API payloads into Spark DataFrames, append them to bronze Delta tables with ingest timestamps and request windows, and publish row-count and latency audit queries so the team can prove data is landing continuously.",
            "expected_deliverable": "Query-ready bronze Delta tables for market and metadata feeds, plus published SQL evidence that append-mode ingestion and request-window tracking are working.",
            "business_why": "Bronze persistence is the control point that moves the campaign from fragile nightly batch pulls to a repeatable market-monitoring foundation.",
            "milestone_tags": ["bronze", "pipeline", "architecture"],
            "resources": [{"title": "Databricks Delta Lake Documentation", "url": "https://docs.databricks.com/en/delta/index.html"}],
            "acceptance_checks": ["Bronze Delta tables published and queryable via SQL", "Append-mode ingestion validated with row-count and request-window audit evidence"],
        },
        {
            "name": "Silver flattening and financial accuracy",
            "duration_weeks": 2,
            "deliverables": ["flattened silver tables", "dedupe logic", "timestamp conversions"],
            "execution_plan": "Flatten CoinGecko JSON fields in PySpark, convert UNIX timestamps into TimestampType, cast price measures to DecimalType for financial accuracy, and implement merge-based deduplication so repeated pulls do not create duplicate silver records.",
            "expected_deliverable": "Silver tables with flattened market metadata, standardized timestamps, deduplicated records, and published merge logic for accurate financial reporting.",
            "business_why": "The finance workflow depends on precise timestamps and deduplicated prices before rolling donation velocity metrics can be trusted.",
            "milestone_tags": ["silver", "pipeline", "data quality"],
            "resources": [{"title": "PySpark SQL Functions Reference", "url": "https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/functions.html"}],
            "acceptance_checks": ["UNIX timestamps converted and DecimalType price fields validated", "Merge or upsert logic published with duplicate-handling test evidence"],
        },
        {
            "name": "Gold velocity monitor and liquidation alerts",
            "duration_weeks": 1,
            "deliverables": ["gold alert table", "rolling average logic", "director dashboard"],
            "execution_plan": f"Build gold tables that calculate 5-minute rolling averages, latency-to-market metrics, and threshold alert flags when current price exceeds the trailing average by 5%; then publish the director dashboard in {serving_tool} for liquidation and compute-cost monitoring.",
            "expected_deliverable": f"Gold Delta marts and a {serving_tool} dashboard that show rolling market averages, pipeline latency in seconds, compute-cost context, and high-value liquidation alert flags for the donation-monitor scenario.",
            "business_why": "Director-level stakeholders need a clear signal for when market conditions justify action on donated crypto assets.",
            "milestone_tags": ["gold", "roi", "bi"],
            "resources": [{"title": "PySpark Window Functions", "url": "https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/window.html"}],
            "acceptance_checks": ["5-minute rolling average logic validated against sample window calculations", "Threshold alert flag published and dashboard latency metric recorded in stakeholder review"],
        },
    ]
    return {
        "project_title": project_title,
        "business_outcome": {
            "problem_statement": "Global Giving Network cannot time crypto asset liquidation effectively because donation-market signals arrive through nightly batch reports with no real-time price checks, no latency KPI, and no alert threshold tied to market conditions.",
            "current_state": "Finance and nonprofit operations teams review stale crypto price snapshots and donation activity after the fact, missing windows where liquidation would protect portfolio value or unlock campaign funds faster.",
            "future_state": "A near real-time medallion pipeline monitors CoinGecko market data, computes donation velocity and rolling averages, and triggers director-ready alert signals when liquidation thresholds are met.",
            "target_metrics": [
                {"metric": "pipeline_latency_seconds", "target": "<90"},
                {"metric": "high_value_alert_coverage", "target": ">=95% of qualifying events"},
                {"metric": "manual_monitoring_reduction", "target": ">=30%"},
            ],
            "domain_focus": ["finance", "crypto", "nonprofit"],
            "data_sources": selected_sources,
        },
        "solution_architecture": {
            "ingestion": {
                "source_pattern": "API-first Python requests ingestion from CoinGecko endpoints into bronze with request metadata and retry-safe logging.",
                "cadence": "1-minute to 5-minute market polling for price checks and periodic metadata refresh for market context.",
            },
            "processing": {
                "engine": "PySpark plus SQL transformations in Databricks",
                "orchestration": "Notebook-driven ingestion with retry logic, Delta append paths, merge-based deduplication, and latency monitoring.",
            },
            "storage": {
                "bronze": "Raw CoinGecko JSON payloads with ingest timestamps, request windows, and status-code evidence.",
                "silver": "Flattened price and market metadata tables with standardized timestamps, DecimalType price fields, and dedupe controls.",
                "gold": "Director-facing marts for 5-minute rolling averages, donation velocity proxies, latency metrics, and liquidation alert flags.",
            },
            "serving": {
                "tool": serving_tool,
                "connection": serving_connection,
            },
            "medallion_plan": {
                "bronze": "Call CoinGecko endpoints with Python requests, store raw JSON strings in bronze Delta tables, and persist request metadata so every market pull can be audited and replayed.",
                "silver": "Flatten nested JSON into top-level Spark columns, convert UNIX timestamps, cast prices as DecimalType, and merge duplicate rows to preserve financial accuracy.",
                "gold": "Calculate 5-minute moving averages, 1-hour comparison baselines, latency-to-market metrics, and threshold alert flags that indicate when donated crypto assets should be reviewed for liquidation.",
            },
            "primary_tools": all_tools,
            "target_skills": all_skills,
        },
        "project_story": {
            "executive_summary": "Global Giving Network Market & Donation Velocity Monitor replaces nightly crypto reporting with a near real-time bronze, silver, and gold pipeline that tracks market prices, latency KPI performance, and liquidation-alert thresholds for a Crypto for Good campaign.",
            "challenge": "Finance and nonprofit leaders were reacting to stale market snapshots, missing 5% price movement windows, and lacking a director-ready dashboard that explained whether current prices, latency seconds, and donation velocity justified action.",
            "approach": f"Build an API-first Databricks pipeline with Python requests, JSON flattening in PySpark, Delta bronze and silver tables, and a {serving_tool} gold dashboard that surfaces rolling averages, alert flags, and compute-cost context.",
            "impact_story": "The project targets a sub-90-second latency KPI, a 30% reduction in manual monitoring, and a measurable improvement in how quickly the nonprofit can identify high-value liquidation opportunities.",
        },
        "milestones": milestones,
        "roi_dashboard_requirements": {
            "required_dimensions": ["timestamp_5min", "symbol", "campaign", "alert_status", "compute_window"],
            "required_measures": ["spot_price", "rolling_average_5min", "latency_seconds", "alert_count", "cluster_minutes"],
            "business_questions": [
                "What is the current pipeline latency in seconds behind the live market?",
                "Which donated assets currently exceed the rolling-average alert threshold and require liquidation review?",
                "How much cluster time or compute cost is being used relative to the volume of market events processed?",
            ],
            "visual_requirements": [
                "Include KPI cards for latency seconds, active alert count, and current market price.",
                "Show a trend of spot price versus 5-minute rolling average with alert-state markers.",
                "Highlight compute minutes alongside processed market-event volume for director-level cost review.",
            ],
            "primary_kpi": "Pipeline Latency Seconds",
        },
        "project_charter_sections": {
            "prerequisites_resources": {
                "summary": "Before kickoff, confirm CoinGecko API access assumptions, Databricks workspace setup, and the candidate's readiness for Python requests, PySpark JSON flattening, and financial timestamp handling.",
                "data_assets": [
                    {
                        "name": "CoinGecko live market feed",
                        "url": (selected_sources[0].get("url") if selected_sources else ""),
                        "ingestion_doc_url": (selected_sources[0].get("ingestion_doc_url") if selected_sources else ""),
                        "action": "Review the CoinGecko endpoint documentation, define polling cadence and request parameters, and document how raw JSON lands in bronze before financial calculations begin.",
                    }
                ],
                "tools": [
                    {"name": "Databricks", "url": "https://www.databricks.com/learn/free-edition"},
                    {"name": "Python Requests", "url": "https://requests.readthedocs.io/en/latest/"},
                    {"name": serving_tool, "url": dashboard_resource["url"]},
                ],
                "skill_check": "The candidate should be comfortable calling REST APIs in Python, flattening nested JSON with PySpark, and explaining rolling averages, latency KPIs, and threshold alerts in business language.",
                "resources": [
                    {"title": "CoinGecko Markets API Reference", "url": "https://docs.coingecko.com/v3.0.1/reference/coins-markets"},
                    {"title": "Databricks Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"},
                ],
            },
            "executive_summary": {
                "current_state": "Nightly batch-style market monitoring leaves the campaign team blind to fast-moving crypto conditions and forces manual review of stale donation-market snapshots.",
                "future_state": "Directors consume near real-time alert dashboards with rolling averages, latency metrics, and threshold-based liquidation signals backed by audited Delta tables.",
            },
            "technical_architecture": {
                "platform": "Databricks lakehouse using Python requests, PySpark, Delta tables, and BI serving for real-time finance monitoring.",
                "ingestion": {
                    "source": "CoinGecko simple price and market metadata endpoints with request-window tracking.",
                    "pattern": "Retry-safe Python ingestion into bronze JSON tables with status-code logging and ingestion timestamps.",
                },
                "processing": {
                    "engine": "PySpark plus SQL transformations",
                    "logic": "Flatten nested market data, convert UNIX timestamps, cast prices to DecimalType, and maintain merge-based silver deduplication before gold alert calculations.",
                },
                "storage": {
                    "bronze": "Raw API JSON payloads with request metadata and latency evidence.",
                    "silver": "Flattened, deduplicated market and metadata tables with standardized timestamps.",
                    "gold": "Rolling average, latency, compute-cost, and high-value alert marts for director reporting.",
                },
                "serving": {
                    "tool": serving_tool,
                    "connection": serving_connection,
                },
                "data_sources": selected_sources[:2],
            },
            "implementation_plan": {
                "milestones": [
                    {
                        "name": "API connectivity and bronze controls",
                        "expectations": "CoinGecko endpoints, retry logic, and bronze landing evidence are documented and working.",
                        "completion_criteria": ["Live payload captured", "Retry logic validated", "Bronze tables queryable"],
                        "estimated_effort_hours": 5,
                        "key_concept": "API resilience",
                    },
                    {
                        "name": "Silver financial standardization",
                        "expectations": "Flattened market records, accurate timestamps, and dedupe logic are published for finance-safe downstream use.",
                        "completion_criteria": ["Decimal price fields validated", "Timestamp conversions published", "Merge logic documented"],
                        "estimated_effort_hours": 6,
                        "key_concept": "Financial data quality",
                    },
                    {
                        "name": "Gold alerting and executive dashboard",
                        "expectations": "Rolling averages, latency metrics, and liquidation alerts support director-level decision making and portfolio storytelling.",
                        "completion_criteria": ["Rolling-average logic validated", "Alert dashboard published", "Stakeholder review recorded"],
                        "estimated_effort_hours": 5,
                        "key_concept": "Real-time alert analytics",
                    },
                ],
            },
            "deliverables_acceptance_criteria": {
                "deliverables": ["Databricks API notebook", "Bronze/Silver/Gold Delta pipeline", "Director alert dashboard", "Narrated market-monitor walkthrough"],
                "acceptance_criteria": ["Live API connectivity is recorded", "Latency KPI is measurable in seconds", "Threshold alerts trace to source market data"],
            },
            "risks_assumptions": {
                "risks": ["CoinGecko rate limits may affect high-frequency polling", "Free-edition compute quotas may pause the cluster", "Donation-velocity proxy logic may need calibration against campaign behavior"],
                "assumptions": ["Public API endpoints remain available", "Candidate can work in Databricks notebooks and explain financial alert logic clearly"],
            },
            "stretch_goals": {
                "items": ["Add Slack or email alert simulation", "Track 1-hour rolling baseline variance", "Publish a one-page director brief summarizing liquidation logic"],
            },
        },
        "interview_story": {
            "challenge": "The campaign team needed faster crypto market visibility to avoid missing high-value liquidation windows.",
            "approach": f"Built a Databricks bronze-to-gold pipeline over CoinGecko APIs, flattened JSON in PySpark, and surfaced latency and alert KPIs in {serving_tool}.",
            "impact_story": "Delivered a realistic real-time finance analytics story with measurable latency improvements and clear decision support for nonprofit operations.",
        },
    }


def _build_general_archetype(
    intake: dict[str, Any],
    all_skills: list[str],
    all_tools: list[str],
    all_domains: list[str],
    selected_sources: list[dict[str, str]],
    serving_tool: str,
) -> dict[str, Any]:
    project_title = f"{(intake.get('applicant_name') or 'Candidate')} - Northbeam Analytics Delivery Program"
    serving_connection = "validated Tableau extracts and executive workbooks with documented KPI definitions" if serving_tool == "Tableau" else "gold marts and published Power BI semantic models with documented KPI definitions"
    dashboard_resource = {"title": "Tableau Blueprint", "url": "https://help.tableau.com/current/guides/en-us/guidance.htm"} if serving_tool == "Tableau" else {"title": "Power BI Design Guidance", "url": "https://learn.microsoft.com/en-us/power-bi/guidance/"}
    milestones = [
        {
            "name": "Discovery and KPI framing",
            "duration_weeks": 1,
            "deliverables": ["scope brief", "KPI dictionary"],
            "execution_plan": "Interview stakeholders, document source systems and report pain points, and convert the findings into a current-state/future-state charter with a prioritized KPI list.",
            "expected_deliverable": "Signed scope brief with KPI ownership, source inventory, and review cadence.",
            "business_why": "A high-quality project needs a clear operational decision problem before technical implementation begins.",
            "milestone_tags": ["discovery", "architecture", "roi"],
            "resources": [{"title": "Kimball Dimensional Modeling", "url": "https://www.kimballgroup.com/data-warehouse-business-intelligence-resources/"}],
            "acceptance_checks": ["Current and future state approved by sponsor", "KPI ownership matrix published with source owners and review cadence"],
        },
        {
            "name": "Pipeline implementation and quality controls",
            "duration_weeks": 2,
            "deliverables": ["ingestion jobs", "transformation tests"],
            "execution_plan": "Land source data in bronze, standardize core entities in silver, and enforce validation checks before publishing any gold metrics or executive views.",
            "expected_deliverable": "Documented bronze-to-gold pipeline with quality checks and failure handling guidance.",
            "business_why": "Trustworthy decision support depends on reliable source ingestion and clear transformation logic.",
            "milestone_tags": ["bronze", "silver", "pipeline"],
            "resources": [{"title": "Delta Lake Medallion Architecture", "url": "https://docs.databricks.com/en/lakehouse/medallion.html"}],
            "acceptance_checks": ["Critical data quality tests pass in CI", "Source-to-gold lineage validated in runbook and architecture notes"],
        },
        {
            "name": "Dashboard release and stakeholder walkthrough",
            "duration_weeks": 1,
            "deliverables": ["semantic model", "dashboard package"],
            "execution_plan": f"Publish gold marts and a {serving_tool} dashboard that answers sponsor business questions, then record a walkthrough and produce concise handoff documentation.",
            "expected_deliverable": "Executive-ready dashboard and portfolio-ready project summary.",
            "business_why": "The final output must show measurable business value, not just technical completeness.",
            "milestone_tags": ["gold", "roi", "bi"],
            "resources": [dashboard_resource],
            "acceptance_checks": ["Dashboard walkthrough recorded and published for stakeholders", "Metric definitions validated against gold tables"],
        },
    ]
    return {
        "project_title": project_title,
        "business_outcome": {
            "problem_statement": "Business leaders lack a reliable KPI view because operational data arrives on inconsistent cadences and downstream reporting relies on manual cleanup before each review.",
            "current_state": "Teams reconcile source exports by hand, slowing down decision cycles and undermining confidence in reported metrics.",
            "future_state": "A governed medallion pipeline publishes trusted gold KPIs with clear lineage, ownership, and executive-ready reporting.",
            "target_metrics": [
                {"metric": "dashboard_refresh_latency", "target": "<2 hours"},
                {"metric": "manual_rework_reduction", "target": ">=25%"},
                {"metric": "stakeholder_dashboard_adoption", "target": ">=60%"},
            ],
            "domain_focus": all_domains or ["analytics"],
            "data_sources": selected_sources,
        },
        "solution_architecture": {
            "ingestion": {
                "source_pattern": "Scheduled API and flat-file landing into bronze with run metadata.",
                "cadence": "Daily or hourly depending on source criticality.",
            },
            "processing": {
                "engine": "PySpark plus SQL/dbt transformations",
                "orchestration": "Workflow scheduling with schema-drift alerts and rerun procedures.",
            },
            "storage": {
                "bronze": "Raw payloads and files with ingest metadata.",
                "silver": "Conformed entities with quality enforcement.",
                "gold": "Stakeholder-facing KPI marts and metric logic.",
            },
            "serving": {
                "tool": serving_tool,
                "connection": serving_connection,
            },
            "medallion_plan": {
                "bronze": "Land source files or API payloads with load metadata, file hashes, and replay checkpoints.",
                "silver": "Standardize core entities, enforce quality tests, and quarantine duplicates or schema drift.",
                "gold": "Publish executive KPI marts with semantic definitions versioned in Git and reviewed by stakeholders.",
            },
            "primary_tools": all_tools,
            "target_skills": all_skills,
        },
        "project_story": {
            "executive_summary": "Northbeam Analytics Delivery Program gives business leaders a 2-hour KPI refresh by landing API and flat-file datasets into bronze, standardizing silver entities, and publishing gold dashboard tables with documented metric definitions.",
            "challenge": "Stakeholders operate with 18-hour to 36-hour report delays, manually reconciled KPI spreadsheets, and limited visibility into the source-system drivers behind business performance changes.",
            "approach": f"Implement bronze ingestion, silver quality gates, and gold KPI marts backed by a documented {serving_tool} reporting layer, measurable acceptance checks, and a formal metric dictionary.",
            "impact_story": "The project targets a 25% reduction in manual reconciliation, a measurable 2-hour dashboard SLA, and a stronger portfolio narrative tied to business-ready KPI outcomes.",
        },
        "milestones": milestones,
        "roi_dashboard_requirements": {
            "required_dimensions": ["time", "business_unit", "region", "product_or_service"],
            "required_measures": ["kpi_primary", "sla_compliance", "exception_rate", "adoption_rate"],
            "business_questions": [
                "Which business units are missing targets and why?",
                "Where is data delay or exception volume undermining decision quality?",
                "What operational pattern best explains the primary KPI trend this month?",
            ],
            "visual_requirements": [
                "Include a KPI card for the primary business metric.",
                "Show a trend view with a business-unit drill-down.",
                "Highlight high-risk segments with clear executive annotation.",
            ],
            "primary_kpi": "Primary KPI",
        },
        "project_charter_sections": {
            "prerequisites_resources": {
                "summary": "Before starting, confirm source documentation, tool setup, and the candidate's readiness for SQL, Python, and KPI storytelling.",
                "data_assets": [
                    {
                        "name": "Primary source set",
                        "url": (selected_sources[0].get("url") if selected_sources else ""),
                        "ingestion_doc_url": (selected_sources[0].get("ingestion_doc_url") if selected_sources else ""),
                        "action": "Review the source documentation, confirm access assumptions, and define how the feed lands in bronze before implementation starts.",
                    }
                ],
                "tools": [
                    {"name": "GitHub", "url": "https://docs.github.com/en/get-started/using-github/github-flow"},
                    {"name": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
                    {"name": serving_tool, "url": dashboard_resource["url"]},
                ],
                "skill_check": "The candidate should be able to explain SQL joins, pipeline layers, and KPI definitions in plain business language.",
                "resources": [
                    {"title": "GitHub Flow", "url": "https://docs.github.com/en/get-started/using-github/github-flow"},
                    {"title": "dbt Documentation", "url": "https://docs.getdbt.com/docs/introduction"},
                ],
            },
            "executive_summary": {
                "current_state": "Reporting is delayed, teams reconcile metrics manually, and leaders cannot trust operating numbers without spreadsheet cleanup.",
                "future_state": "Decision makers consume trusted KPIs from a documented gold layer with clear SLAs, metric ownership, and drill-down context.",
            },
            "technical_architecture": {
                "platform": "Medallion architecture with orchestration, quality gates, and semantic layer.",
                "ingestion": {
                    "source": "Operational APIs plus flat-file extracts or selected public datasets depending on the project scenario.",
                    "pattern": "Replay-safe bronze ingestion with load metadata and documented cadence.",
                },
                "processing": {
                    "engine": "PySpark plus SQL/dbt transformations",
                    "logic": "Conformance, quality checks, schema-drift handling, and dimensional KPI modeling.",
                },
                "storage": {
                    "bronze": "Raw payloads or files with ingest metadata.",
                    "silver": "Conformed entities with data quality enforcement.",
                    "gold": "Stakeholder-facing KPI marts and metric logic.",
                },
                "serving": {
                    "tool": serving_tool,
                    "connection": serving_connection,
                },
                "data_sources": selected_sources[:2],
            },
            "implementation_plan": {
                "milestones": [
                    {
                        "name": "Foundation and source onboarding",
                        "expectations": "Ingestion contracts, source access notes, pipeline scaffolding, and validation checks are in place.",
                        "completion_criteria": ["Source landed in bronze", "Validation queries are green", "Runbook checked in"],
                        "estimated_effort_hours": 3,
                        "key_concept": "Idempotent ingestion",
                    },
                    {
                        "name": "Silver standardization and quality controls",
                        "expectations": "Core entities are standardized with explicit quality rules, naming conventions, and grain decisions.",
                        "completion_criteria": ["DQ thresholds enforced", "Critical entities are conformed", "Transformation rules documented"],
                        "estimated_effort_hours": 4,
                        "key_concept": "Schema enforcement",
                    },
                    {
                        "name": "Gold KPI layer and dashboard narrative",
                        "expectations": "Gold marts and dashboard outputs answer clear business questions and tie back to measurable outcomes.",
                        "completion_criteria": ["Critical KPI logic reviewed", "Dashboard reconciles to source", "Stakeholder sign-off recorded"],
                        "estimated_effort_hours": 4,
                        "key_concept": "Executive KPI storytelling",
                    },
                ],
            },
            "deliverables_acceptance_criteria": {
                "deliverables": ["Architecture diagram", "Pipelines plus tests", "Executive dashboard", "Demo narrative"],
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
        "interview_story": {
            "challenge": "Stakeholders were stuck reconciling late reports and could not trust the KPI narrative before leadership reviews.",
            "approach": f"Built a bronze-to-gold analytics pipeline with quality gates and a documented {serving_tool} reporting layer.",
            "impact_story": "Produced a realistic business-facing data engineering project with measurable operational value and a clear interview narrative.",
        },
    }



def _humanize_assessment_key(key: str) -> str:
    return str(key or "").replace("_", " ").strip().title()


def _summarize_self_assessment(preferences: dict[str, Any]) -> dict[str, Any]:
    assessment = (preferences or {}).get("self_assessment") or {}
    scored = [
        (str(key), float(value))
        for key, value in (assessment or {}).items()
        if isinstance(value, (int, float))
    ]
    strongest = [_humanize_assessment_key(key) for key, value in scored if value >= 4][:3]
    weakest = [_humanize_assessment_key(key) for key, value in scored if value <= 2][:3]
    notes = str((assessment or {}).get("notes") or "").strip()
    return {
        "strongest": strongest,
        "weakest": weakest,
        "notes": notes[:500],
    }


def _resolve_llm_api_key() -> tuple[str, str]:
    openai_api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if openai_api_key:
        return openai_api_key, "OPENAI_API_KEY"
    llm_api_key = (os.getenv("LLM_API_KEY") or "").strip()
    if llm_api_key:
        return llm_api_key, "LLM_API_KEY"
    return "", "none"


def _infer_requested_industry(intake: dict[str, Any], parsed_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    preferences = intake.get("preferences") or {}
    resume_summary = (preferences.get("resume_parse_summary") or {}) if isinstance(preferences, dict) else {}

    raw_domains: list[str] = []
    for domain in (resume_summary.get("domains") or []):
        value = str(domain or "").strip()
        if value:
            raw_domains.append(value)
    for job in (parsed_jobs or []):
        signals = job.get("signals") or {}
        for domain in (signals.get("domains") or []):
            value = str(domain or "").strip()
            if value:
                raw_domains.append(value)

    normalized = [domain.lower() for domain in raw_domains if domain.strip()]
    deduped: list[str] = []
    for domain in normalized:
        if domain not in deduped:
            deduped.append(domain)

    primary = deduped[0] if deduped else "general"
    source = "resume_or_job_domains" if deduped else "fallback_general"
    return {
        "primary": primary,
        "all_domains": deduped or ["general"],
        "source": source,
    }


def _build_project_strategy_fallback(intake: dict[str, Any], parsed_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    preferences = intake.get("preferences") or {}
    resume_summary = (preferences.get("resume_parse_summary") or {}) if isinstance(preferences, dict) else {}
    all_tools = sorted(({
        str(s).strip().lower()
        for p in (parsed_jobs or [])
        for s in ((p.get("signals") or {}).get("tools") or [])
        if str(s).strip()
    } | {
        str(s).strip().lower() for s in (resume_summary.get("tools") or []) if str(s).strip()
    }))
    all_domains = sorted(({
        str(s).strip().lower()
        for p in (parsed_jobs or [])
        for s in ((p.get("signals") or {}).get("domains") or [])
        if str(s).strip()
    } | {
        str(s).strip().lower() for s in (resume_summary.get("domains") or []) if str(s).strip()
    }))
    scope_profile = _derive_scope_profile(intake=intake, parsed_jobs=parsed_jobs)
    archetype = _infer_project_archetype(intake=intake, parsed_jobs=parsed_jobs, all_domains=all_domains, all_tools=all_tools)
    selected_sources = _select_data_sources(intake=intake, parsed_jobs=parsed_jobs)
    self_summary = _summarize_self_assessment(preferences)
    requested_industry = _infer_requested_industry(intake=intake, parsed_jobs=parsed_jobs)

    project_focus_map = {
        "retail": "Design a margin, inventory, and returns intelligence project that feels like a consulting charter for store and channel leadership.",
        "energy": "Design an operations-focused resilience project using telemetry, weather, and risk scoring to support proactive decisions.",
        "finance": "Design a near real-time market monitoring and alerting project with financial precision, latency tracking, and threshold-based business actions.",
        "general": "Design a realistic bronze, silver, and gold analytics program with clear business KPIs, stakeholder workflow, and portfolio-ready delivery evidence.",
    }
    business_problem_map = {
        "retail": "Conflicting channel metrics and delayed inventory insight make it hard for leaders to act on margin pressure and stockout risk.",
        "energy": "Disconnected telemetry and weather signals make it hard for operators to see outage exposure and utilization risk early enough to respond.",
        "finance": "Nightly reporting leaves campaign and finance leaders blind to fast-moving crypto conditions and high-value liquidation opportunities.",
        "general": "Fragmented source systems and manual reconciliation delay KPI visibility and weaken stakeholder trust in the reporting process.",
    }
    dashboard_questions_map = {
        "retail": [
            "Which stores or channels are driving the largest KPI decline this week?",
            "Where is inventory or return behavior creating operational or margin risk?",
            "What action should leadership take next based on the current dashboard signals?",
        ],
        "energy": [
            "Which regions or sites have the highest operational risk right now?",
            "How do telemetry freshness and external conditions change the risk story?",
            "What intervention should the operations team prioritize next?",
        ],
        "finance": [
            "What is the current pipeline latency in seconds behind the live market?",
            "Which assets or market events meet the alert threshold right now?",
            "How much compute time is being used relative to the monitoring value created?",
        ],
        "general": [
            "Which KPI is underperforming and why?",
            "Where is the operational or revenue risk concentrated?",
            "What action should the stakeholder take next?",
        ],
    }

    candidate_fit_summary = f"Target role level is {scope_profile.get('target_role_level')} with {scope_profile.get('scope_difficulty')} scope. Resume signals emphasize {', '.join((resume_summary.get('tools') or [])[:4]) or 'core analytics engineering skills'}."
    if self_summary.get("strongest"):
        candidate_fit_summary += f" Strongest self-assessed areas: {', '.join(self_summary.get('strongest') or [])}."
    if self_summary.get("weakest"):
        candidate_fit_summary += f" Areas to reinforce in the project: {', '.join(self_summary.get('weakest') or [])}."

    return {
        "archetype": archetype,
        "candidate_fit_summary": candidate_fit_summary,
        "project_focus": project_focus_map.get(archetype, project_focus_map["general"]),
        "business_problem": business_problem_map.get(archetype, business_problem_map["general"]),
        "recommended_source_names": [str(src.get("name") or "") for src in selected_sources if str(src.get("name") or "")][:3],
        "requested_industry": requested_industry.get("primary") or "general",
        "dashboard_questions": dashboard_questions_map.get(archetype, dashboard_questions_map["general"]),
        "delivery_scope": {
            "target_role_level": scope_profile.get("target_role_level"),
            "scope_difficulty": scope_profile.get("scope_difficulty"),
            "suggested_timeline_weeks": scope_profile.get("suggested_timeline_weeks"),
            "serving_tool": _preferred_serving_tool(all_tools),
        },
        "self_assessment_takeaways": {
            "strongest": self_summary.get("strongest") or [],
            "weakest": self_summary.get("weakest") or [],
            "notes": self_summary.get("notes") or "",
        },
        "resume_evidence": {
            "tools": resume_summary.get("tools") or [],
            "domains": resume_summary.get("domains") or [],
            "project_keywords": resume_summary.get("project_experience_keywords") or [],
        },
        "industry_context": requested_industry,
    }


def _coerce_project_strategy(strategy: dict[str, Any] | None, intake: dict[str, Any], parsed_jobs: list[dict[str, Any]]) -> dict[str, Any]:
    fallback = _build_project_strategy_fallback(intake=intake, parsed_jobs=parsed_jobs)
    if not isinstance(strategy, dict):
        return fallback

    merged = dict(fallback)
    archetype = str(strategy.get("archetype") or fallback.get("archetype") or "general").strip().lower()
    if archetype not in {"retail", "energy", "finance", "general"}:
        archetype = str(fallback.get("archetype") or "general")
    merged["archetype"] = archetype

    for key in ["candidate_fit_summary", "project_focus", "business_problem", "requested_industry"]:
        value = str(strategy.get(key) or "").strip()
        if value:
            merged[key] = value

    source_names = [str(x).strip() for x in (strategy.get("recommended_source_names") or []) if str(x).strip()][:3]
    if source_names:
        merged["recommended_source_names"] = source_names

    dashboard_questions = [str(x).strip() for x in (strategy.get("dashboard_questions") or []) if str(x).strip()][:3]
    if len(dashboard_questions) >= 3:
        merged["dashboard_questions"] = dashboard_questions

    if isinstance(strategy.get("delivery_scope"), dict):
        merged_scope = dict(merged.get("delivery_scope") or {})
        for key in ["target_role_level", "scope_difficulty", "suggested_timeline_weeks", "serving_tool"]:
            value = strategy.get("delivery_scope", {}).get(key)
            if value not in {None, ""}:
                merged_scope[key] = value
        merged["delivery_scope"] = merged_scope

    if isinstance(strategy.get("self_assessment_takeaways"), dict):
        merged_takeaways = dict(merged.get("self_assessment_takeaways") or {})
        for key in ["strongest", "weakest"]:
            values = [str(x).strip() for x in (strategy.get("self_assessment_takeaways", {}).get(key) or []) if str(x).strip()]
            if values:
                merged_takeaways[key] = values[:3]
        notes = str(strategy.get("self_assessment_takeaways", {}).get("notes") or "").strip()
        if notes:
            merged_takeaways["notes"] = notes[:500]
        merged["self_assessment_takeaways"] = merged_takeaways

    if isinstance(strategy.get("industry_context"), dict):
        merged_industry = dict(merged.get("industry_context") or {})
        for key in ["primary", "source"]:
            value = str(strategy.get("industry_context", {}).get(key) or "").strip()
            if value:
                merged_industry[key] = value
        domains = [
            str(x).strip().lower()
            for x in (strategy.get("industry_context", {}).get("all_domains") or [])
            if str(x).strip()
        ]
        if domains:
            merged_industry["all_domains"] = domains
        merged["industry_context"] = merged_industry

    return merged


def _request_llm_json(
    *,
    client: httpx.Client,
    base_url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_payload: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    body = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload)},
        ],
        "response_format": {"type": "json_object"},
    }
    resp = client.post(
        f"{base_url}/chat/completions",
        json=body,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    resp.raise_for_status()
    payload = resp.json()
    content = (((payload.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}")
    return _safe_json_loads(content), payload

def generate_sow_with_llm(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
    timeout: int = 45,
    max_retries: int = 2,
) -> dict[str, Any]:
    api_key, api_key_source = _resolve_llm_api_key()
    model = ("gpt-5.4").strip() #os.getenv("COACHING_SOW_LLM_MODEL") or
    base_url = (os.getenv("OPENAI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    strategy_fallback = _build_project_strategy_fallback(intake=intake, parsed_jobs=parsed_jobs)
    requested_industry = _infer_requested_industry(intake=intake, parsed_jobs=parsed_jobs)

    if not api_key:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY / LLM_API_KEY missing",
            "sow": build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs, project_strategy=strategy_fallback),
            "meta": {
                "provider": "scaffold",
                "model": "fallback",
                "base_url": base_url,
                "api_key_source": api_key_source,
                "error_type": "provider",
                "reason_code": "LLM_API_KEY_MISSING",
                "strategy": {
                    "provider": "fallback",
                    "reason_code": "STRATEGY_STAGE_NOT_RUN",
                    "project_strategy": strategy_fallback,
                },
            },
        }

    candidate_preferences = intake.get("preferences") or {}
    prompt_payload_base = {
        "candidate": {
            "name": intake.get("applicant_name"),
            "preferences": candidate_preferences,
            "resume_text": str(intake.get("resume_text") or "")[:4000],
            "self_assessment_text": str(intake.get("self_assessment_text") or "")[:4000],
            "self_assessment_structured": (candidate_preferences.get("self_assessment") or {}) if isinstance(candidate_preferences, dict) else {},
        },
        "parsed_jobs": parsed_jobs[:8],
        "industry_context": requested_industry,
        "style_anchors": STYLE_ANCHORS,
    }

    attempts = 0
    last_error = "unknown_error"
    error_type = "provider"
    reason_code = "LLM_PROVIDER_ERROR"
    while attempts <= max_retries:
        attempts += 1
        try:
            with httpx.Client(timeout=timeout) as client:
                project_strategy = dict(strategy_fallback)
                strategy_meta = {
                    "provider": "fallback",
                    "reason_code": "STRATEGY_STAGE_FALLBACK",
                    "project_strategy": dict(strategy_fallback),
                }
                strategy_error_message = None

                strategy_request_payload = {
                    **prompt_payload_base,
                    "available_archetypes": ["retail", "energy", "finance", "general"],
                    "required_contract": {
                        "required_keys": [
                            "archetype",
                            "candidate_fit_summary",
                            "project_focus",
                            "business_problem",
                            "recommended_source_names",
                            "requested_industry",
                            "dashboard_questions",
                            "delivery_scope",
                            "self_assessment_takeaways",
                            "industry_context",
                        ],
                        "hard_rules": [
                            "Return JSON only",
                            "Choose one archetype from retail, energy, finance, general",
                            "Use resume, self-assessment, and target job signals to decide project direction",
                            "Use the exact keys from output_template",
                            "Do not rename keys or wrap the response in another object",
                            "dashboard_questions must be concrete business questions",
                            "recommended_source_names should reference likely public data sources or API families",
                            "requested_industry must reflect the best-fit business domain for source selection",
                        ],
                    },
                    "output_template": {
                        "archetype": "general",
                        "candidate_fit_summary": "Explain why this candidate is a strong fit for the project.",
                        "project_focus": "Describe the portfolio-ready project direction.",
                        "business_problem": "State the measurable business problem.",
                        "recommended_source_names": ["Named source family 1", "Named source family 2"],
                        "requested_industry": requested_industry.get("primary") or "general",
                        "dashboard_questions": [
                            "Concrete business question 1",
                            "Concrete business question 2",
                            "Concrete business question 3",
                        ],
                        "delivery_scope": {
                            "target_role_level": "mid",
                            "scope_difficulty": "standard",
                            "suggested_timeline_weeks": 6,
                            "serving_tool": "Power BI",
                        },
                        "self_assessment_takeaways": {
                            "strongest": ["Example strength"],
                            "weakest": ["Example growth area"],
                            "notes": "Optional coaching note.",
                        },
                        "industry_context": requested_industry,
                    },
                }
                try:
                    strategy_response, strategy_payload = _request_llm_json(
                        client=client,
                        base_url=base_url,
                        api_key=api_key,
                        model=model,
                        system_prompt="You are a senior data engineering coaching strategist. Return exactly one JSON object using the exact keys in output_template. Do not add wrapper objects, markdown, commentary, or alternate key names. Analyze the candidate's resume, self-assessment, target jobs, and requested industry context to choose the best project direction before the full charter is generated.",
                        user_payload=strategy_request_payload,
                    )
                    project_strategy = _coerce_project_strategy(strategy_response, intake=intake, parsed_jobs=parsed_jobs)
                    strategy_meta = {
                        "provider": "openai-compatible",
                        "reason_code": "STRATEGY_STAGE_OK",
                        "usage": strategy_payload.get("usage") or {},
                        "finish_reason": (((strategy_payload.get("choices") or [{}])[0].get("finish_reason")) or ""),
                        "project_strategy": project_strategy,
                    }
                except httpx.HTTPStatusError as e:
                    strategy_error_message = f"strategy_http_{int(e.response.status_code)}"
                except httpx.TimeoutException:
                    strategy_error_message = "strategy_timeout"
                except httpx.RequestError:
                    strategy_error_message = "strategy_network_error"
                except json.JSONDecodeError:
                    strategy_error_message = "strategy_json_decode_error"
                except Exception as e:
                    strategy_error_message = str(e) or "strategy_unknown_error"

                if strategy_error_message:
                    strategy_meta = {
                        "provider": "fallback",
                        "reason_code": "STRATEGY_STAGE_FAILED",
                        "error": strategy_error_message,
                        "project_strategy": project_strategy,
                    }

                prompt_payload = {
                    **prompt_payload_base,
                    "project_strategy": project_strategy,
                    "style_brief": {
                        "tone": "premium consulting charter",
                        "voice": "specific, executive-ready, implementation-realistic",
                        "anchors": STYLE_ANCHORS,
                    },
                    "content_expectations": {
                        "industry_alignment": f"Favor data sources, KPIs, and business language that match the requested industry: {requested_industry.get('primary') or 'general'}.",
                        "data_source_justification": "Every data source must include selection_rationale explaining why it belongs in the project and the charter.",
                        "story_quality": "Use a fictitious but realistic company, business unit, and operating context with concrete systems, cadence, and measurable value.",
                    },
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
                        "business_outcome_required": ["problem_statement", "current_state", "future_state", "target_metrics", "domain_focus", "data_sources"],
                        "data_source_shape": {
                            "name": "string",
                            "url": "https://real-link",
                            "ingestion_doc_url": "https://real-doc-link",
                            "selection_rationale": "why this source belongs in the project",
                            "ingestion_instructions": "explicit step-by-step instructions",
                        },
                        "milestone_shape": {
                            "name": "string", "duration_weeks": "int>=1", "deliverables": ["string"],
                            "execution_plan": "string", "expected_deliverable": "string", "business_why": "string",
                            "milestone_tags": ["string"], "resources": [{"title": "string", "url": "https://real-link"}], "acceptance_checks": ["string"],
                        },
                        "project_story_required": ["executive_summary", "challenge", "approach", "impact_story"],
                        "roi_required": ["required_dimensions", "required_measures", "business_questions", "visual_requirements"],
                        "resources_required": ["required", "recommended", "optional", "affiliate_disclosure", "trust_language"],
                        "project_charter_required": {
                            "section_order": list(CHARTER_REQUIRED_SECTION_FLOW),
                            "executive_summary_fields": ["current_state", "future_state"],
                            "prerequisites_resources_fields": ["summary", "data_assets", "tools", "skill_check", "resources"],
                            "technical_architecture_requires": ["ingestion", "processing", "storage", "serving", "data_sources with url + ingestion_doc_url + selection_rationale + ingestion_instructions"],
                            "implementation_plan_requires": ["milestones with expectations + completion_criteria + estimated_effort_hours + key_concept"],
                        },
                        "hard_rules": [
                            "Return exactly one JSON object using the exact keys from output_template",
                            "Do not rename keys, add wrapper objects, or emit markdown",
                            "Keep content personalized to candidate resume/preferences/target roles",
                            "Honor the supplied project_strategy and requested industry as the planning brief",
                            "Use realistic fictitious business context with measurable KPI impact",
                            "Do not echo prompt/schema meta language in the output",
                            "Each data source must include url, ingestion_doc_url, selection_rationale, and explicit ingestion_instructions",
                            "At least 3 milestones with execution_plan, expected_deliverable, business_why, resources, and acceptance_checks",
                            "project_charter.section_order must match project_charter_required.section_order",
                        ],
                    },
                    "output_template": build_sow_skeleton(
                        intake={"applicant_name": "Example Candidate", "preferences": {}},
                        parsed_jobs=[],
                        project_strategy={
                            "requested_industry": requested_industry.get("primary") or "general",
                            "industry_context": requested_industry,
                        },
                    ),
                }

                sow, payload = _request_llm_json(
                    client=client,
                    base_url=base_url,
                    api_key=api_key,
                    model=model,
                    system_prompt="You are a senior data engineering consulting partner. Return exactly one production-grade SOW JSON object using the exact structure and key names in output_template. Do not add wrapper objects, markdown, commentary, or alternate shapes. Write in a premium consulting-charter style with realistic fictitious business context, concrete implementation detail, explicit data-source justifications, and KPI-driven outcomes aligned to the supplied project_strategy and requested industry.",
                    user_payload=prompt_payload,
                )
                sow = normalize_generated_sow(sow)

            structure = evaluate_sow_structure(sow)
            if structure.get("missing_sections") or not structure.get("order_valid"):
                last_error = "LLM output failed required structure contract"
                error_type = "schema"
                reason_code = "LLM_SCHEMA_INVALID"
                if attempts <= max_retries:
                    continue
                break

            review_meta: dict[str, Any] = {
                "attempted": False,
                "applied": False,
                "reason": "disabled",
            }
            review_enabled = str(os.getenv("COACHING_SOW_ENABLE_REVIEW_PASS") or "1").strip().lower() not in {"0", "false", "no", "off"}
            if review_enabled:
                review_meta = {
                    "attempted": True,
                    "applied": False,
                    "reason": "no_improvement",
                }
                try:
                    findings_before = validate_sow_payload(sow)
                    quality_before = compute_sow_quality_score(sow, findings_before)
                    review_payload = {
                        "candidate": prompt_payload_base.get("candidate") or {},
                        "project_strategy": project_strategy,
                        "draft_sow": sow,
                        "draft_quality": {
                            "score": int(quality_before.get("score") or 0),
                            "finding_count": int(quality_before.get("finding_count") or 0),
                            "findings": findings_before[:20],
                        },
                        "required_contract": prompt_payload.get("required_contract") or {},
                        "hard_rules": [
                            "Return JSON only",
                            "Preserve required top-level section order and contract shape",
                            "Increase specificity: KPI thresholds, milestone acceptance checks, data source ingestion instructions",
                            "Do not include prompt/schema meta language in output",
                        ],
                    }
                    reviewed_sow, review_resp = _request_llm_json(
                        client=client,
                        base_url=base_url,
                        api_key=api_key,
                        model=model,
                        system_prompt="You are a principal QA editor for premium data engineering project charters. Critique the draft SOW against the contract and improve weak sections while preserving valid structure. Return only improved SOW JSON.",
                        user_payload=review_payload,
                    )
                    reviewed_sow = normalize_generated_sow(reviewed_sow)
                    reviewed_structure = evaluate_sow_structure(reviewed_sow)
                    if not reviewed_structure.get("missing_sections") and reviewed_structure.get("order_valid"):
                        findings_after = validate_sow_payload(reviewed_sow)
                        quality_after = compute_sow_quality_score(reviewed_sow, findings_after)
                        improved = (
                            int(quality_after.get("score") or 0) > int(quality_before.get("score") or 0)
                            or int(quality_after.get("finding_count") or 0) < int(quality_before.get("finding_count") or 0)
                        )
                        review_meta = {
                            "attempted": True,
                            "applied": bool(improved),
                            "reason": "improved" if improved else "no_improvement",
                            "quality_before": quality_before,
                            "quality_after": quality_after,
                            "review_finish_reason": (((review_resp.get("choices") or [{}])[0].get("finish_reason")) or ""),
                            "usage": review_resp.get("usage") or {},
                        }
                        if improved:
                            sow = reviewed_sow
                    else:
                        review_meta = {
                            "attempted": True,
                            "applied": False,
                            "reason": "review_schema_invalid",
                        }
                except Exception as review_error:
                    review_meta = {
                        "attempted": True,
                        "applied": False,
                        "reason": "review_error",
                        "error": str(review_error),
                    }

            return {
                "ok": True,
                "sow": sow,
                "meta": {
                    "provider": "openai-compatible",
                    "model": model,
                    "base_url": base_url,
                    "api_key_source": api_key_source,
                    "usage": payload.get("usage") or {},
                    "finish_reason": (((payload.get("choices") or [{}])[0].get("finish_reason")) or ""),
                    "attempts": attempts,
                    "error_type": None,
                    "generation_pipeline": "analysis_then_charter",
                    "strategy": strategy_meta,
                    "review": review_meta,
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
        "sow": build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs, project_strategy=strategy_fallback),
        "meta": {
            "provider": "scaffold",
            "model": model,
            "base_url": base_url,
            "api_key_source": api_key_source,
            "attempts": attempts,
            "error_type": error_type,
            "reason_code": reason_code,
            "generation_pipeline": "analysis_then_charter",
            "strategy": {
                "provider": "fallback",
                "reason_code": "STRATEGY_STAGE_FALLBACK",
                "project_strategy": strategy_fallback,
            },
            "review": {
                "attempted": False,
                "applied": False,
                "reason": "generator_fallback",
            },
        },
    }

def build_sow_skeleton(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
    project_strategy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resume_summary = ((intake.get("preferences") or {}).get("resume_parse_summary") or {}) if isinstance((intake.get("preferences") or {}), dict) else {}
    all_skills = sorted({str(s).strip().lower() for p in parsed_jobs for s in p.get("signals", {}).get("skills", []) if str(s).strip()})
    all_tools = sorted(({str(s).strip().lower() for p in parsed_jobs for s in p.get("signals", {}).get("tools", []) if str(s).strip()} | {str(s).strip().lower() for s in (resume_summary.get("tools") or []) if str(s).strip()}))
    all_domains = sorted(({str(s).strip().lower() for p in parsed_jobs for s in p.get("signals", {}).get("domains", []) if str(s).strip()} | {str(s).strip().lower() for s in (resume_summary.get("domains") or []) if str(s).strip()}))

    scope_profile = _derive_scope_profile(intake=intake, parsed_jobs=parsed_jobs)
    strategy = _coerce_project_strategy(project_strategy, intake=intake, parsed_jobs=parsed_jobs) if project_strategy else {}
    serving_tool = str(((strategy.get("delivery_scope") or {}).get("serving_tool") or "")).strip() or _preferred_serving_tool(all_tools)
    archetype = str(strategy.get("archetype") or "").strip().lower() or _infer_project_archetype(intake=intake, parsed_jobs=parsed_jobs, all_domains=all_domains, all_tools=all_tools)
    selected_sources = _select_data_sources(intake=intake, parsed_jobs=parsed_jobs)
    strategy_source_names = [str(x).strip() for x in (strategy.get("recommended_source_names") or []) if str(x).strip()]
    if strategy_source_names:
        selected_sources = _ensure_data_sources(selected_sources, strategy_source_names)

    if archetype == "retail":
        selected_sources = _ensure_data_sources(selected_sources, ["Sample Superstore Sales Dataset", "Bureau of Labor Statistics Public Data API", "NYC TLC Trip Record Data"])
        payload = _build_retail_archetype(intake=intake, all_skills=all_skills, all_tools=all_tools, selected_sources=selected_sources, serving_tool=serving_tool)
    elif archetype == "energy":
        selected_sources = _ensure_data_sources(selected_sources, ["Open Charge Map API", "OpenWeather One Call API", "Bureau of Labor Statistics Public Data API"])
        payload = _build_energy_archetype(intake=intake, all_skills=all_skills, all_tools=all_tools, selected_sources=selected_sources, serving_tool=serving_tool)
    elif archetype == "finance":
        selected_sources = _ensure_data_sources(selected_sources, ["CoinGecko Simple Price API", "CoinGecko Markets API", "Bureau of Labor Statistics Public Data API"])
        payload = _build_finance_archetype(intake=intake, all_skills=all_skills, all_tools=all_tools, selected_sources=selected_sources, serving_tool=serving_tool)
    else:
        payload = _build_general_archetype(intake=intake, all_skills=all_skills, all_tools=all_tools, all_domains=all_domains, selected_sources=selected_sources, serving_tool=serving_tool)

    if strategy:
        strategy_questions = [str(x).strip() for x in (strategy.get("dashboard_questions") or []) if str(x).strip()]
        if len(strategy_questions) >= 3:
            payload.setdefault("roi_dashboard_requirements", {})["business_questions"] = strategy_questions[:3]

    project_title = payload["project_title"]
    interview_story = payload.get("interview_story") or {}

    return {
        "schema_version": "0.2",
        "project_title": project_title,
        "candidate_profile": {
            "applicant_name": intake.get("applicant_name"),
            "preferences": intake.get("preferences") or {},
            "role_scope_assessment": scope_profile,
        },
        "business_outcome": payload["business_outcome"],
        "solution_architecture": payload["solution_architecture"],
        "project_story": payload["project_story"],
        "milestones": payload["milestones"],
        "roi_dashboard_requirements": payload["roi_dashboard_requirements"],
        "resource_plan": _build_common_resource_plan(serving_tool),
        "mentoring_cta": {
            "recommended_tier": "starter" if scope_profile.get("scope_difficulty") == "foundational" else ("elite" if scope_profile.get("scope_difficulty") == "advanced" else "core"),
            "reason": f"Mapped from resume/job signals: current={scope_profile.get('current_role_level')} target={scope_profile.get('target_role_level')} scope={scope_profile.get('scope_difficulty')}.",
            "trust_language": "Mentoring recommendations are guidance-only and should align with the candidate's goals and budget.",
        },
        "project_charter": {
            "section_order": list(CHARTER_REQUIRED_SECTION_FLOW),
            "sections": payload["project_charter_sections"],
        },
        "interview_ready_package": _build_interview_ready_package(
            project_title=project_title,
            story={
                "challenge": interview_story.get("challenge") or payload["project_story"].get("challenge") or "",
                "approach": interview_story.get("approach") or payload["project_story"].get("approach") or "",
                "impact_story": interview_story.get("impact_story") or payload["project_story"].get("impact_story") or "",
            },
            milestones=payload["milestones"],
            tools=all_tools,
        ),
    }



