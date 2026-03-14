from __future__ import annotations

import os
from typing import Any
import re

from security import mask_secrets_in_text

from .constants import REQUIRED_SECTION_FLOW, CHARTER_REQUIRED_SECTION_FLOW
from .sow_security import sanitize_generated_sow, _is_valid_non_placeholder_url


def _build_interview_ready_package(project_title: str, story: dict[str, Any], milestones: list[dict[str, Any]], tools: list[str]) -> dict[str, Any]:
    safe_title = mask_secrets_in_text(str(project_title or "Project"))
    challenge = mask_secrets_in_text(str((story or {}).get("challenge") or "Translate ambiguous business requirements into reliable data outcomes."))
    approach = mask_secrets_in_text(str((story or {}).get("approach") or "Use iterative delivery with measurable acceptance criteria and stakeholder demos."))
    impact = mask_secrets_in_text(str((story or {}).get("impact_story") or "Deliver KPI improvements with reproducible implementation evidence."))

    milestone_names = [str(m.get("name") or "Milestone") for m in (milestones or []) if isinstance(m, dict)]
    star_bullets = [
        f"Situation: {challenge}",
        f"Task: Own delivery of {safe_title} milestones with clear KPI targets.",
        f"Action: {approach}",
        f"Result: {impact}",
    ]
    portfolio_checklist = [
        "Architecture diagram exported and narrated in README",
        "Pipeline tests + data quality checks committed with run evidence",
        "Executive KPI dashboard with metric dictionary and assumptions",
        "Demo script + retrospective including trade-offs and next steps",
    ]
    recruiter_mapping = {
        "technical_depth": milestone_names[:3],
        "business_impact": [impact],
        "communication": ["Executive summary", "STAR narrative", "Demo walkthrough"],
        "tooling_keywords": sorted({str(t) for t in (tools or []) if str(t).strip()}),
    }
    return {
        "star_bullets": star_bullets,
        "portfolio_checklist": portfolio_checklist,
        "recruiter_mapping": recruiter_mapping,
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


def _normalize_charter_sections(
    charter: dict[str, Any],
    business_outcome: dict[str, Any],
    solution_architecture: dict[str, Any],
    milestones: list[dict[str, Any]],
    project_story: dict[str, Any],
    resource_plan: dict[str, Any],
) -> dict[str, Any]:
    sections = charter.get("sections")
    if isinstance(sections, dict):
        out = dict(sections)
    else:
        out = {}

    alternate_keys = {
        "prerequisites_resources": "prerequisites_resources_fields",
        "executive_summary": "executive_summary_fields",
        "technical_architecture": "technical_architecture_requires",
        "implementation_plan": "implementation_plan_requires",
    }
    for section_name, alternate_key in alternate_keys.items():
        if section_name not in out and isinstance(charter.get(alternate_key), dict):
            out[section_name] = dict(charter.get(alternate_key) or {})

    if not isinstance(out.get("prerequisites_resources"), dict):
        out["prerequisites_resources"] = {}
    prereq = out["prerequisites_resources"]
    if not str(prereq.get("summary") or "").strip():
        prereq["summary"] = "Confirm source access, tooling setup, and stakeholder readiness before delivery starts."
    if not prereq.get("resources"):
        prereq["resources"] = list(resource_plan.get("required") or [])
    if not str(prereq.get("skill_check") or "").strip():
        prereq["skill_check"] = "Candidate should be comfortable with SQL, Python, and explaining KPI trade-offs to stakeholders."

    if not isinstance(out.get("executive_summary"), dict):
        out["executive_summary"] = {}
    exec_summary = out["executive_summary"]
    if not str(exec_summary.get("current_state") or "").strip():
        exec_summary["current_state"] = str((business_outcome.get("current_state") or project_story.get("challenge") or "")).strip()
    if not str(exec_summary.get("future_state") or "").strip():
        exec_summary["future_state"] = str((business_outcome.get("future_state") or project_story.get("impact_story") or "")).strip()

    if not isinstance(out.get("technical_architecture"), dict):
        out["technical_architecture"] = {}
    tech_arch = out["technical_architecture"]
    for key in ["ingestion", "processing", "storage", "serving"]:
        if not tech_arch.get(key) and solution_architecture.get(key):
            tech_arch[key] = solution_architecture.get(key)
    if not tech_arch.get("data_sources") and business_outcome.get("data_sources"):
        tech_arch["data_sources"] = list(business_outcome.get("data_sources") or [])

    if not isinstance(out.get("implementation_plan"), dict):
        out["implementation_plan"] = {}
    impl = out["implementation_plan"]
    if not impl.get("milestones") and milestones:
        impl["milestones"] = [
            {
                "name": str(ms.get("name") or "Milestone"),
                "expected_deliverable": str(ms.get("expected_deliverable") or ", ".join(ms.get("deliverables") or []) or ""),
                "completion_criteria": list(ms.get("acceptance_checks") or []),
                "estimated_effort_hours": max(8, int(ms.get("duration_weeks") or 1) * 20),
                "key_concept": str(ms.get("business_why") or ms.get("execution_plan") or ""),
            }
            for ms in milestones
            if isinstance(ms, dict)
        ]

    if not isinstance(out.get("deliverables_acceptance_criteria"), dict):
        out["deliverables_acceptance_criteria"] = {
            "milestones": [
                {
                    "name": str(ms.get("name") or "Milestone"),
                    "deliverables": list(ms.get("deliverables") or []),
                    "acceptance_checks": list(ms.get("acceptance_checks") or []),
                }
                for ms in milestones
                if isinstance(ms, dict)
            ]
        }

    if not isinstance(out.get("risks_assumptions"), dict):
        out["risks_assumptions"] = {
            "risks": [
                "Source-system access or API quotas may delay initial ingestion validation.",
                "Claims metric definitions may need stakeholder sign-off before dashboard publication.",
            ],
            "assumptions": [
                "Required source credentials and sandbox access will be available during the first sprint.",
                "Business owners can validate KPI definitions during milestone reviews.",
            ],
        }

    if not isinstance(out.get("stretch_goals"), dict):
        out["stretch_goals"] = {
            "summary": "Add stretch deliverables only after the core pipeline, KPI validation, and dashboard acceptance checks are complete.",
        }

    return out


def normalize_generated_sow(sow: dict[str, Any]) -> dict[str, Any]:
    out = dict(sow or {})
    business_outcome = out.get("business_outcome")
    if not isinstance(business_outcome, dict):
        business_outcome = {}
    out["business_outcome"] = business_outcome

    domain_focus = business_outcome.get("domain_focus")
    if isinstance(domain_focus, str) and domain_focus.strip():
        business_outcome["domain_focus"] = [domain_focus.strip()]

    solution_architecture = out.get("solution_architecture")
    if not isinstance(solution_architecture, dict):
        solution_architecture = {}
    out["solution_architecture"] = solution_architecture

    medallion = solution_architecture.get("medallion_plan")
    if not isinstance(medallion, dict):
        medallion = {}
    if not str(medallion.get("bronze") or "").strip():
        medallion["bronze"] = str(solution_architecture.get("ingestion") or "Land raw source extracts into a replay-safe Bronze layer.").strip()
    if not str(medallion.get("silver") or "").strip():
        medallion["silver"] = str(solution_architecture.get("processing") or "Clean, standardize, and quality-check records in Silver.").strip()
    if not str(medallion.get("gold") or "").strip():
        gold_parts = [str(solution_architecture.get("storage") or "").strip(), str(solution_architecture.get("serving") or "").strip()]
        medallion["gold"] = " ".join(part for part in gold_parts if part) or "Publish KPI-ready marts and dashboard-facing aggregates in Gold."
    solution_architecture["medallion_plan"] = medallion

    mentoring_cta = out.get("mentoring_cta")
    if isinstance(mentoring_cta, str):
        out["mentoring_cta"] = {"reason": mentoring_cta}
    elif not isinstance(mentoring_cta, dict):
        out["mentoring_cta"] = {}

    milestones = out.get("milestones")
    if not isinstance(milestones, list):
        milestones = []
    out["milestones"] = milestones

    project_story = out.get("project_story")
    if not isinstance(project_story, dict):
        project_story = {}
    out["project_story"] = project_story

    resource_plan = out.get("resource_plan")
    if not isinstance(resource_plan, dict):
        resource_plan = {}
    canonical_resource_urls = {
        "azure data factory": "https://learn.microsoft.com/azure/data-factory/introduction",
        "databricks": "https://docs.databricks.com/",
        "azure synapse": "https://learn.microsoft.com/azure/synapse-analytics/",
        "azure synapse analytics": "https://learn.microsoft.com/azure/synapse-analytics/",
        "power bi": "https://learn.microsoft.com/power-bi/",
        "github": "https://github.com/",
        "slack": "https://slack.com/",
        "tableau": "https://www.tableau.com/",
    }
    for bucket in ["required", "recommended", "optional"]:
        normalized_bucket: list[dict[str, Any]] = []
        for item in (resource_plan.get(bucket) or []):
            if isinstance(item, dict):
                normalized_bucket.append(dict(item))
                continue
            title = str(item or "").strip()
            if not title:
                continue
            url = ""
            lowered = title.lower()
            for key, candidate_url in canonical_resource_urls.items():
                if key in lowered:
                    url = candidate_url
                    break
            normalized_bucket.append({"title": title, "url": url})
        resource_plan[bucket] = normalized_bucket
    out["resource_plan"] = resource_plan

    charter = out.get("project_charter")
    if not isinstance(charter, dict):
        charter = {}
    charter["sections"] = _normalize_charter_sections(
        charter=charter,
        business_outcome=business_outcome,
        solution_architecture=solution_architecture,
        milestones=milestones,
        project_story=project_story,
        resource_plan=resource_plan,
    )
    charter["section_order"] = list(CHARTER_REQUIRED_SECTION_FLOW)
    out["project_charter"] = charter

    return enforce_required_section_order(out)


def ensure_interview_ready_package(sow: dict[str, Any]) -> dict[str, Any]:
    out = dict(sow or {})
    package = out.get("interview_ready_package")
    if not isinstance(package, dict):
        package = {}

    built = _build_interview_ready_package(
        project_title=str(out.get("project_title") or "Project"),
        story=out.get("project_story") or {},
        milestones=out.get("milestones") or [],
        tools=((out.get("solution_architecture") or {}).get("primary_tools") or []),
    )

    if not isinstance(package.get("star_bullets"), list) or len(package.get("star_bullets") or []) < 4:
        package["star_bullets"] = built["star_bullets"]
    else:
        package["star_bullets"] = [mask_secrets_in_text(str(x or "")) for x in (package.get("star_bullets") or [])]
    if not isinstance(package.get("portfolio_checklist"), list) or len(package.get("portfolio_checklist") or []) < 3:
        package["portfolio_checklist"] = built["portfolio_checklist"]
    else:
        package["portfolio_checklist"] = [mask_secrets_in_text(str(x or "")) for x in (package.get("portfolio_checklist") or [])]

    recruiter_mapping = package.get("recruiter_mapping") if isinstance(package.get("recruiter_mapping"), dict) else {}
    built_mapping = built.get("recruiter_mapping") or {}
    for key in ["technical_depth", "business_impact", "communication"]:
        if not isinstance(recruiter_mapping.get(key), list) or len(recruiter_mapping.get(key) or []) == 0:
            recruiter_mapping[key] = built_mapping.get(key) or []
        else:
            recruiter_mapping[key] = [mask_secrets_in_text(str(x or "")) for x in (recruiter_mapping.get(key) or [])]
    existing_keywords = recruiter_mapping.get("tooling_keywords")
    if isinstance(existing_keywords, list) and existing_keywords:
        recruiter_mapping["tooling_keywords"] = [mask_secrets_in_text(str(x or "")) for x in existing_keywords if str(x or "").strip()]
    else:
        recruiter_mapping["tooling_keywords"] = built_mapping.get("tooling_keywords") or []
    package["recruiter_mapping"] = recruiter_mapping

    out["interview_ready_package"] = package
    return out


def enforce_required_section_order(sow: dict[str, Any]) -> dict[str, Any]:
    ordered: dict[str, Any] = {}
    payload = sow or {}
    for key in REQUIRED_SECTION_FLOW:
        if key in payload:
            ordered[key] = payload[key]
    for key, value in payload.items():
        if key not in ordered:
            ordered[key] = value
    return ordered


_INSTRUCTION_ECHO_PATTERNS = [
    r"\breturn\s+json\s+only\b",
    r"\bno\s+markdown\b",
    r"\btop_level_order_required\b",
    r"\brequired_contract\b",
    r"\bhard_rules\b",
    r"\bstyle_anchors\b",
    r"project_title\s*->\s*candidate\s+profile\s+context",
    r"produce\s+production-grade\s+sow\s+json",
]

_GENERIC_SCAFFOLD_PHRASES = [
    "build a job-aligned medallion data platform project",
    "translate fragmented source data into trusted kpi reporting",
    "demonstrate end-to-end ownership from ingestion through business narrative",
    "define a measurable business problem and target kpi uplift",
]

_LEGACY_STORY_MARKERS = {
    "northbeam",
    "northbeam outfitters",
    "blueorbit",
    "blueorbit home services",
}

_DOMAIN_SIGNAL_MAP = {
    "retail": {
        "resume_markers": {"retail", "ecommerce", "merchandising", "inventory", "omnichannel", "customer"},
        "source_markers": {"kaggle", "superstore", "instacart", "olist", "retail"},
        "kpi_markers": {"basket", "margin", "aov", "conversion", "sell-through", "returns", "inventory turns"},
    },
    "energy": {
        "resume_markers": {"energy", "utilities", "ev", "charging", "grid", "outage", "telemetry", "resilience"},
        "source_markers": {"open charge map", "openweather", "eia", "entsoe", "nrel"},
        "kpi_markers": {"downtime", "uptime", "outage", "charger", "load", "forecast error", "station utilization"},
    },
    "finance": {
        "resume_markers": {"finance", "trading", "crypto", "market", "donation", "risk", "fraud"},
        "source_markers": {"coingecko", "federal reserve", "fred", "sec", "alphavantage", "iex"},
        "kpi_markers": {"latency", "volatility", "drawdown", "slippage", "alert", "donation velocity", "liquidation"},
    },
}


def _enforce_domain_archetype_validation() -> bool:
    raw = str(os.getenv("COACHING_ENFORCE_DOMAIN_ARCHETYPE_VALIDATION") or "0").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _contains_instruction_echo(text: str) -> bool:
    low = str(text or "").lower()
    return any(re.search(pattern, low) for pattern in _INSTRUCTION_ECHO_PATTERNS)


def _looks_generic_scaffold(text: str) -> bool:
    low = str(text or "").strip().lower()
    if not low:
        return True
    if any(phrase in low for phrase in _GENERIC_SCAFFOLD_PHRASES):
        return True
    # Strong concrete signals: numbers, named systems, explicit business entities.
    concrete_signals = ["%", "kpi", "sla", "api", "dataset", "table", "warehouse", "bronze", "silver", "gold", "dashboard", "hours", "minutes", "weekly", "monthly"]
    has_signal = any(sig in low for sig in concrete_signals) or bool(re.search(r"\b\d+(?:\.\d+)?\b", low))
    vague_markers = ["generic", "placeholder", "job-aligned", "candidate", "data project", "business outcomes"]
    return (not has_signal) or any(marker in low for marker in vague_markers)


def _infer_expected_domain_family(resume_summary: dict[str, Any], domain_focus: list[str], project_strategy: dict[str, Any]) -> str:
    strategy_domain = str(project_strategy.get("archetype") or "").strip().lower()
    if strategy_domain in _DOMAIN_SIGNAL_MAP:
        return strategy_domain

    terms = {
        str(item).strip().lower()
        for item in ((resume_summary.get("domains") or []) + (resume_summary.get("project_experience_keywords") or []) + (domain_focus or []))
        if str(item).strip()
    }
    for domain_name, signals in _DOMAIN_SIGNAL_MAP.items():
        if terms.intersection(signals["resume_markers"]):
            return domain_name
    return ""


def validate_sow_payload(sow: dict[str, Any]) -> list[dict[str, str]]:
    sow = normalize_generated_sow(sow)
    sow, safety_findings = sanitize_generated_sow(sow)
    sow = ensure_interview_ready_package(sow)
    sow = enforce_required_section_order(sow)
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

    charter = sow.get("project_charter") or {}
    charter_sections = charter.get("sections") or {}
    charter_order = charter.get("section_order") or []
    missing_charter = [section for section in CHARTER_REQUIRED_SECTION_FLOW if section not in charter_sections]
    if missing_charter:
        findings.append({"code": "CHARTER_SECTION_MISSING", "message": f"project_charter.sections missing: {', '.join(missing_charter)}"})
    if list(charter_order) != list(CHARTER_REQUIRED_SECTION_FLOW):
        findings.append({"code": "CHARTER_SECTION_ORDER_INVALID", "message": "project_charter.section_order must match required charter flow exactly."})
    tech_arch = charter_sections.get("technical_architecture") or {}
    for idx, src in enumerate((tech_arch.get("data_sources") or [])):
        if not _is_valid_non_placeholder_url(str(src.get("url") or "")):
            findings.append({"code": "CHARTER_DATA_SOURCE_URL_INVALID", "message": f"project_charter.sections.technical_architecture.data_sources[{idx}].url must be a real link."})
        if not _is_valid_non_placeholder_url(str(src.get("ingestion_doc_url") or "")):
            findings.append({"code": "CHARTER_INGESTION_DOC_URL_INVALID", "message": f"project_charter.sections.technical_architecture.data_sources[{idx}].ingestion_doc_url must be a real link."})
        if not str(src.get("selection_rationale") or "").strip():
            findings.append({"code": "CHARTER_DATA_SOURCE_RATIONALE_MISSING", "message": f"project_charter.sections.technical_architecture.data_sources[{idx}].selection_rationale is required."})

    medallion = ((sow.get("solution_architecture") or {}).get("medallion_plan") or {})
    for layer in ["bronze", "silver", "gold"]:
        if not str(medallion.get(layer) or "").strip():
            findings.append({"code": "MEDALLION_INCOMPLETE", "message": f"Missing medallion layer detail: {layer}"})

    story = sow.get("project_story") or {}
    for k in ["executive_summary", "challenge", "approach", "impact_story"]:
        if not str(story.get(k) or "").strip():
            findings.append({"code": "PROJECT_STORY_MISSING", "message": f"project_story.{k} is required."})
    story_text = " ".join(str(story.get(k) or "") for k in ["executive_summary", "challenge", "approach", "impact_story"])
    low_story = story_text.lower()
    if len(story_text.strip()) < 320:
        findings.append({"code": "PROJECT_STORY_DEPTH_WEAK", "message": "project_story should include richer executive depth (current state, approach detail, and quantified impact)."})
    if not any(token in low_story for token in ["kpi", "%", "sla", "minutes", "revenue", "cost", "uptime", "adoption"]):
        findings.append({"code": "PROJECT_STORY_METRIC_SIGNAL_MISSING", "message": "project_story should reference measurable KPI or operational impact signals."})
    if _contains_instruction_echo(story_text):
        findings.append({"code": "INSTRUCTION_ECHO_DETECTED", "message": "project_story appears to echo prompt/meta instructions instead of business narrative."})
    for k in ["executive_summary", "challenge", "approach", "impact_story"]:
        section = str(story.get(k) or "")
        if _looks_generic_scaffold(section):
            findings.append({"code": "PROJECT_STORY_GENERIC", "message": f"project_story.{k} is too generic; include concrete business context, systems, and measurable outcomes."})

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
        if not str(ds.get("ingestion_instructions") or "").strip():
            findings.append({"code": "INGESTION_INSTRUCTIONS_MISSING", "message": f"data_sources[{i}].ingestion_instructions are required."})
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

            ms_text = " ".join(str(ms.get(k) or "") for k in ["name", "execution_plan", "expected_deliverable", "business_why"])
            if _contains_instruction_echo(ms_text):
                findings.append({"code": "INSTRUCTION_ECHO_DETECTED", "message": f"milestones[{i}] appears to echo prompt instructions/meta text."})
            if _looks_generic_scaffold(str(ms.get("execution_plan") or "")):
                findings.append({"code": "MILESTONE_GENERIC_EXECUTION", "message": f"milestones[{i}].execution_plan is generic; include concrete systems, steps, and evidence outputs."})
            if _looks_generic_scaffold(str(ms.get("expected_deliverable") or "")):
                findings.append({"code": "MILESTONE_GENERIC_DELIVERABLE", "message": f"milestones[{i}].expected_deliverable is generic; define measurable artifact quality and acceptance evidence."})
            checks = ms.get("acceptance_checks") or []
            non_empty_checks = [str(c).strip() for c in checks if str(c).strip()]
            if not isinstance(checks, list) or len(non_empty_checks) < 2:
                findings.append({"code": "MILESTONE_ACCEPTANCE_CHECKS_MISSING", "message": f"milestones[{i}].acceptance_checks must include at least 2 concrete checks."})
            else:
                measurable = [c for c in non_empty_checks if len(c) >= 12 and any(tok in c.lower() for tok in ["pass", "approved", "signed", "validated", "recorded", "published", "measured"])]
                if len(measurable) < 2:
                    findings.append({"code": "MILESTONE_ACCEPTANCE_CHECKS_NOT_ACTIONABLE", "message": f"milestones[{i}].acceptance_checks should be measurable and verification-ready (e.g., signed off, tests passed, metric validated)."})
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

    interview = sow.get("interview_ready_package") or {}
    if not isinstance(interview.get("star_bullets"), list) or len(interview.get("star_bullets") or []) < 4:
        findings.append({"code": "INTERVIEW_STAR_BULLETS_INCOMPLETE", "message": "interview_ready_package.star_bullets must include at least 4 STAR bullets."})
    if not isinstance(interview.get("portfolio_checklist"), list) or len(interview.get("portfolio_checklist") or []) < 3:
        findings.append({"code": "INTERVIEW_PORTFOLIO_CHECKLIST_INCOMPLETE", "message": "interview_ready_package.portfolio_checklist must include at least 3 checklist items."})
    recruiter_mapping = interview.get("recruiter_mapping") or {}
    for key in ["technical_depth", "business_impact", "communication"]:
        if not isinstance(recruiter_mapping.get(key), list) or len(recruiter_mapping.get(key) or []) == 0:
            findings.append({"code": "INTERVIEW_RECRUITER_MAPPING_INCOMPLETE", "message": f"interview_ready_package.recruiter_mapping.{key} must be non-empty."})

    # Personalization checks: ensure resume/self-assessment evidence actually appears in generated output.
    candidate_profile = sow.get("candidate_profile") or {}
    preferences = candidate_profile.get("preferences") or {}
    resume_summary = preferences.get("resume_parse_summary") or {}
    parse_conf = int(resume_summary.get("parse_confidence") or 0)
    resume_tools = [str(t).strip().lower() for t in (resume_summary.get("tools") or []) if str(t).strip()]
    resume_domains = [str(d).strip().lower() for d in (resume_summary.get("domains") or []) if str(d).strip()]
    resume_project_terms = [str(k).strip().lower() for k in (resume_summary.get("project_experience_keywords") or []) if str(k).strip()]

    if parse_conf >= 55 and (resume_tools or resume_domains or resume_project_terms):
        sow_text_parts = [
            str(sow.get("project_title") or ""),
            " ".join(str(v or "") for v in (sow.get("project_story") or {}).values()),
            " ".join(str(m.get("name") or "") + " " + str(m.get("execution_plan") or "") + " " + str(m.get("business_why") or "") for m in (sow.get("milestones") or []) if isinstance(m, dict)),
            " ".join(str(x or "") for x in ((sow.get("solution_architecture") or {}).get("primary_tools") or [])),
            " ".join(str(x or "") for x in ((sow.get("business_outcome") or {}).get("domain_focus") or [])),
        ]
        sow_text = " ".join(sow_text_parts).lower()

        tracked_signals = list(dict.fromkeys([*resume_tools[:4], *resume_domains[:3], *resume_project_terms[:3]]))
        matched_signals = [sig for sig in tracked_signals if sig and sig in sow_text]

        architecture_tools = [str(t).strip().lower() for t in ((sow.get("solution_architecture") or {}).get("primary_tools") or []) if str(t).strip()]
        outcome_domains = [str(d).strip().lower() for d in ((sow.get("business_outcome") or {}).get("domain_focus") or []) if str(d).strip()]
        explicit_tool_overlap = len(set(resume_tools).intersection(set(architecture_tools)))
        explicit_domain_overlap = len(set(resume_domains).intersection(set(outcome_domains)))

        weak_signal_match = tracked_signals and len(matched_signals) < max(1, min(2, len(tracked_signals) // 2))
        weak_explicit_alignment = bool(resume_tools and resume_domains and explicit_tool_overlap == 0 and explicit_domain_overlap == 0)
        if weak_signal_match and weak_explicit_alignment:
            findings.append(
                {
                    "code": "PERSONALIZATION_SIGNAL_MISSING",
                    "message": "Generated SOW appears weakly personalized versus resume_parse_summary signals; include explicit tool/domain/project evidence from candidate profile.",
                }
            )

        role_level = str(resume_summary.get("role_level") or "").strip().lower()
        scope = (candidate_profile.get("role_scope_assessment") or {}).get("scope_difficulty")
        if role_level == "senior" and str(scope or "").strip().lower() == "foundational":
            findings.append(
                {
                    "code": "PERSONALIZATION_SCOPE_MISMATCH",
                    "message": "role_scope_assessment.scope_difficulty is too low for senior resume signals; adjust milestone depth and scope expectations.",
                }
            )

    combined_text = " ".join(
        [
            str(sow.get("project_title") or ""),
            story_text,
            " ".join(str((ds or {}).get("name") or "") for ds in data_sources if isinstance(ds, dict)),
            " ".join(str(x or "") for x in ((roi.get("business_questions") or []) + (roi.get("required_measures") or []))),
        ]
    ).lower()
    expected_domain = _infer_expected_domain_family(
        resume_summary=resume_summary,
        domain_focus=[str(x).strip().lower() for x in (business.get("domain_focus") or []) if str(x).strip()],
        project_strategy=sow.get("project_strategy") or {},
    )
    enforce_legacy_gate = bool(expected_domain or str((sow.get("project_strategy") or {}).get("archetype") or "").strip())
    if enforce_legacy_gate and any(marker in combined_text for marker in _LEGACY_STORY_MARKERS):
        findings.append(
            {
                "code": "LEGACY_STORY_REUSE_DETECTED",
                "message": "Generated SOW reused legacy story/company markers. Regenerate with a fresh domain-specific narrative.",
            }
        )

    if expected_domain and _enforce_domain_archetype_validation():
        signals = _DOMAIN_SIGNAL_MAP.get(expected_domain) or {}
        source_names = " ".join(str((ds or {}).get("name") or "") for ds in data_sources if isinstance(ds, dict)).lower()
        kpi_text = " ".join(str(x or "") for x in ((roi.get("business_questions") or []) + (roi.get("required_measures") or []) + (business.get("target_metrics") or []))).lower()
        if signals.get("source_markers") and not any(marker in source_names for marker in signals["source_markers"]):
            findings.append({"code": "DOMAIN_SOURCE_MISMATCH", "message": f"Data sources do not align with expected {expected_domain} domain signals."})
        if signals.get("kpi_markers") and not any(marker in kpi_text for marker in signals["kpi_markers"]):
            findings.append({"code": "DOMAIN_KPI_MISMATCH", "message": f"KPI language does not align with expected {expected_domain} domain signals."})
        if signals.get("resume_markers") and not any(marker in combined_text for marker in signals["resume_markers"]):
            findings.append({"code": "DOMAIN_NARRATIVE_MISMATCH", "message": f"Narrative does not align with expected {expected_domain} domain context."})

    return findings


def _style_anchor_alignment_score(sow: dict[str, Any]) -> int:
    story = sow.get("project_story") or {}
    charter = (sow.get("project_charter") or {}).get("sections") or {}
    technical_arch = charter.get("technical_architecture") or {}
    implementation_plan = charter.get("implementation_plan") or {}

    score = 0
    if str((charter.get("executive_summary") or {}).get("current_state") or "").strip():
        score += 20
    if str((charter.get("executive_summary") or {}).get("future_state") or "").strip():
        score += 20
    story_text = " ".join(str(story.get(k) or "") for k in ["executive_summary", "challenge", "approach", "impact_story"]).lower()
    if any(token in story_text for token in ["kpi", "%", "minutes", "sla", "uptime", "cost", "revenue"]):
        score += 20
    if len(technical_arch.get("data_sources") or []) >= 2:
        score += 20
    if len((implementation_plan.get("milestones") or [])) >= 2:
        score += 20
    return max(0, min(100, score))


def _milestone_specificity_score(sow: dict[str, Any]) -> int:
    milestones = sow.get("milestones") or []
    if not isinstance(milestones, list) or len(milestones) == 0:
        return 0

    scored = 0
    for ms in milestones:
        if not isinstance(ms, dict):
            continue
        checks = 0
        for field in ["execution_plan", "expected_deliverable", "business_why"]:
            if len(str(ms.get(field) or "").strip()) >= 40:
                checks += 1
        deliverables = ms.get("deliverables") or []
        if isinstance(deliverables, list) and len(deliverables) >= 2:
            checks += 1
        resources = ms.get("resources") or []
        if isinstance(resources, list) and any(_is_valid_non_placeholder_url(str(r.get("url") or "")) for r in resources if isinstance(r, dict)):
            checks += 1
        scored += checks

    max_score = max(1, len(milestones) * 5)
    return int(round((scored / max_score) * 100))


def compute_sow_quality_score(sow: dict[str, Any], findings: list[dict[str, str]] | None = None) -> dict[str, Any]:
    issues = findings if findings is not None else validate_sow_payload(sow)
    structure = evaluate_sow_structure(sow)
    milestone_specificity = _milestone_specificity_score(sow)
    penalties = min(80, len(issues) * 8)
    content_score = max(0, min(100, 100 - penalties))
    style_alignment_score = _style_anchor_alignment_score(sow)
    score = int(round((0.5 * content_score) + (0.2 * int(structure.get("structure_score") or 0)) + (0.15 * milestone_specificity) + (0.15 * style_alignment_score)))
    return {
        "score": score,
        "threshold_passed": score >= 70,
        "finding_count": len(issues),
        "structure_score": int(structure.get("structure_score") or 0),
        "milestone_specificity_score": milestone_specificity,
        "missing_sections": structure.get("missing_sections") or [],
        "section_order_valid": bool(structure.get("order_valid")),
        "style_alignment_score": style_alignment_score,
    }


def build_quality_diagnostics(
    quality: dict[str, Any],
    findings: list[dict[str, str]],
    floor_score: int = 80,
    auto_regenerated: bool = False,
    workspace_id: str | None = None,
    submission_id: str | None = None,
) -> dict[str, Any]:
    score = int(quality.get("score") or 0)
    codes = [str(f.get("code") or "") for f in findings if str(f.get("code") or "")]
    unique_codes = sorted(set(codes))

    regen_hints_map = {
        "SECTION_ORDER_INVALID": "Regenerate with exact exemplar section order from REQUIRED_SECTION_FLOW.",
        "MISSING_SECTION": "Fill all missing top-level sections before finalizing output.",
        "MILESTONE_EXECUTION_PLAN_MISSING": "Expand milestone execution plans with concrete tasks and acceptance criteria.",
        "MILESTONE_EXPECTED_DELIVERABLE_MISSING": "Define measurable deliverable quality (tests, docs, demo evidence) per milestone.",
        "MILESTONE_BUSINESS_WHY_MISSING": "Tie each milestone to a measurable KPI or business outcome.",
        "MILESTONE_RESOURCES_MISSING": "Add at least one non-placeholder resource URL for each milestone.",
        "DATA_SOURCE_LINK_INVALID": "Use real public data source links (no placeholders/example.com).",
        "INGESTION_DOC_LINK_MISSING": "Add ingestion documentation URLs for every data source.",
        "RESOURCE_LINKS_MISSING": "Populate required/recommended/optional resource plan links.",
        "INGESTION_INSTRUCTIONS_MISSING": "Add explicit ingestion instructions (how/where/frequency) for each data source.",
        "MILESTONE_ACCEPTANCE_CHECKS_MISSING": "Define at least 2 concrete acceptance checks for every milestone.",
        "MILESTONE_ACCEPTANCE_CHECKS_NOT_ACTIONABLE": "Rewrite acceptance checks as measurable verification statements (signed-off, tested, validated, published).",
        "PROJECT_STORY_DEPTH_WEAK": "Deepen project_story with current-state constraints, implementation tradeoffs, and quantified business outcomes.",
        "PROJECT_STORY_METRIC_SIGNAL_MISSING": "Add explicit KPI/operational metrics (SLA, adoption, revenue/cost impact) to project_story narrative.",
        "PROJECT_STORY_GENERIC": "Replace generic project_story wording with a specific fictitious business context, named systems, and quantified targets.",
        "INSTRUCTION_ECHO_DETECTED": "Remove prompt/meta-instruction echoes; return only business content and concrete execution details.",
        "MILESTONE_GENERIC_EXECUTION": "Rewrite milestone execution plans with concrete tasks, systems touched, and validation evidence.",
        "MILESTONE_GENERIC_DELIVERABLE": "Define milestone deliverables as verifiable artifacts (tests, dashboards, docs, demo recording).",
        "PERSONALIZATION_SIGNAL_MISSING": "Reference resume_parse_summary evidence directly in tools, domains, and milestone execution choices.",
        "PERSONALIZATION_SCOPE_MISMATCH": "Rebalance scope_difficulty and timeline so role level, evidence, and milestone depth align.",
        "LEGACY_STORY_REUSE_DETECTED": "Regenerate with a fresh business narrative and prohibit legacy company/story names.",
        "DOMAIN_SOURCE_MISMATCH": "Align data source family with inferred domain archetype.",
        "DOMAIN_KPI_MISMATCH": "Align KPI vocabulary with inferred domain archetype.",
        "DOMAIN_NARRATIVE_MISMATCH": "Align project narrative with inferred domain archetype and resume signals.",
    }
    targeted_regeneration_hints = [regen_hints_map[c] for c in unique_codes if c in regen_hints_map][:6]
    if int(quality.get("structure_score") or 0) < 90:
        targeted_regeneration_hints.append("Regenerate using REQUIRED_SECTION_FLOW headings verbatim and keep top-level order unchanged.")
    if int(quality.get("milestone_specificity_score") or 0) < 75:
        targeted_regeneration_hints.append("For each milestone, include 3-5 concrete implementation tasks, a measurable deliverable, and KPI-linked business impact.")
    if int(quality.get("style_alignment_score") or 0) < 75:
        targeted_regeneration_hints.append("Match GlobalMart/VoltStream charter tone: quantified outcomes, current->future state framing, and risk-aware implementation detail.")
    if score < int(floor_score):
        targeted_regeneration_hints.append("Raise depth: include production-ready artifact detail (tests, docs, runbooks, demo evidence) instead of generic phrasing.")
    targeted_regeneration_hints = list(dict.fromkeys(targeted_regeneration_hints))[:8]

    actionable_fail_reasons = []
    for finding in findings[:8]:
        message = str(finding.get("message") or "")
        path_match = None
        try:
            import re
            path_match = re.search(r"([A-Za-z_]+\[[0-9]+\]\.[A-Za-z_]+|project_charter\.[A-Za-z_\.]+|data_sources\[[0-9]+\]\.[A-Za-z_]+)", message)
        except Exception:
            path_match = None
        actionable_fail_reasons.append(
            {
                "code": str(finding.get("code") or "UNKNOWN"),
                "field": path_match.group(1) if path_match else "sow",
                "reason": mask_secrets_in_text(message),
                "suggested_fix": regen_hints_map.get(str(finding.get("code") or ""), "Address this finding and rerun validation."),
            }
        )

    major_prefixes = (
        "SECTION_",
        "MISSING_SECTION",
        "CHARTER_",
        "DATA_SOURCE_",
        "INGESTION_",
        "MILESTONE_",
        "ROI_",
        "RESOURCE_LINKS_MISSING",
        "INSTRUCTION_",
        "PROJECT_STORY_GENERIC",
        "LEGACY_STORY_REUSE_DETECTED",
        "DOMAIN_",
    )
    major_codes = [code for code in unique_codes if code.startswith(major_prefixes)]

    regenerate_payload = {
        "contract_version": "2026-03-sprint13",
        "endpoint": "/coaching/sow/generate",
        "method": "POST",
        "body": {
            "workspace_id": workspace_id,
            "submission_id": submission_id,
            "parsed_jobs": [],
            "regenerate_with_improvements": True,
            "deficiency_context": {
                "deficiency_codes": unique_codes[:12],
                "major_deficiency_codes": major_codes[:8],
                "targeted_regeneration_hints": targeted_regeneration_hints[:5],
            },
        },
        "requires": ["workspace_id", "submission_id"],
        "optional": ["parsed_jobs", "deficiency_context"],
        "reason_codes": major_codes[:8],
        "hints": targeted_regeneration_hints[:5],
    }

    return {
        "floor_score": floor_score,
        "score": score,
        "below_floor": score < int(floor_score),
        "auto_regenerated": bool(auto_regenerated),
        "deficiency_codes": unique_codes,
        "deficiency_count": len(findings),
        "major_deficiency_codes": major_codes,
        "major_deficiency_count": len(major_codes),
        "top_deficiencies": [mask_secrets_in_text(str(f.get("message") or "")) for f in findings[:5]],
        "actionable_fail_reasons": actionable_fail_reasons,
        "structure_score": int(quality.get("structure_score") or 0),
        "milestone_specificity_score": int(quality.get("milestone_specificity_score") or 0),
        "missing_sections": quality.get("missing_sections") or [],
        "section_order_valid": bool(quality.get("section_order_valid")),
        "style_alignment_score": int(quality.get("style_alignment_score") or 0),
        "targeted_regeneration_hints": targeted_regeneration_hints,
        "recommended_regeneration": bool(score < int(floor_score) or len(major_codes) > 0),
        "regenerate_payload": regenerate_payload,
    }
