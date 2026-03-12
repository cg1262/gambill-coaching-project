from __future__ import annotations

import io
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any


RUBRIC_VERSION = "2026-03-generation-meta-rubric-v1"


def _bounded(value: float) -> int:
    return int(max(0, min(100, round(value))))


def _json_text(payload: Any) -> str:
    try:
        return json.dumps(payload or {}, ensure_ascii=True).lower()
    except Exception:
        return str(payload or "").lower()


def _count_hits(text: str, terms: list[str]) -> int:
    lower = str(text or "").lower()
    return sum(1 for term in terms if term in lower)


def _extract_text_from_docx_bytes(content: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            xml_bytes = zf.read("word/document.xml")
        root = ET.fromstring(xml_bytes)
        texts = [node.text for node in root.iter() if node.tag.endswith("}t") and node.text]
        return " ".join(texts)
    except Exception:
        return ""


def _load_reference_text(path: str) -> tuple[str, str]:
    p = Path(str(path or "").strip()).expanduser()
    if not str(p):
        return "", "empty_path"
    if not p.exists() or not p.is_file():
        return "", "not_found"
    try:
        if p.suffix.lower() in {".md", ".txt"}:
            return p.read_text(encoding="utf-8", errors="ignore"), "ok"
        if p.suffix.lower() == ".docx":
            return _extract_text_from_docx_bytes(p.read_bytes()), "ok"
        return "", "unsupported_type"
    except Exception:
        return "", "read_error"


def _score_scope_clarity(sow: dict[str, Any]) -> tuple[int, list[str]]:
    evidence: list[str] = []
    score = 0
    business = sow.get("business_outcome") or {}
    problem = str(business.get("problem_statement") or "").strip()
    if len(problem) >= 120:
        score += 25
        evidence.append("Problem statement has strong business context depth.")
    elif len(problem) >= 60:
        score += 15
        evidence.append("Problem statement has moderate context depth.")
    else:
        evidence.append("Problem statement is too short for premium charter clarity.")

    metrics = business.get("target_metrics") or []
    metric_text = json.dumps(metrics, ensure_ascii=True)
    if isinstance(metrics, list) and len(metrics) >= 2:
        score += 25
        evidence.append("At least two target metrics are present.")
    elif isinstance(metrics, list) and len(metrics) == 1:
        score += 12
        evidence.append("Only one target metric was provided.")
    num_hits = len(re.findall(r"(\b\d+(\.\d+)?\b|%|>=|<=|<|>)", metric_text))
    score += 15 if num_hits >= 3 else (8 if num_hits >= 1 else 0)

    milestones = sow.get("milestones") or []
    with_business_why = 0
    if isinstance(milestones, list):
        if len(milestones) >= 3:
            score += 15
            evidence.append("Milestone count meets minimum program depth.")
        for m in milestones:
            if str((m or {}).get("business_why") or "").strip():
                with_business_why += 1
    score += 20 if with_business_why >= 3 else (10 if with_business_why > 0 else 0)
    return _bounded(score), evidence


def _score_architecture_depth(sow: dict[str, Any]) -> tuple[int, list[str]]:
    evidence: list[str] = []
    score = 0
    medallion = ((sow.get("solution_architecture") or {}).get("medallion_plan") or {})
    for layer in ["bronze", "silver", "gold"]:
        line = str(medallion.get(layer) or "").strip()
        score += 10 if len(line) >= 40 else (6 if len(line) >= 20 else 0)
    ta_text = _json_text((((sow.get("project_charter") or {}).get("sections") or {}).get("technical_architecture") or {}))
    coverage_hits = _count_hits(ta_text, ["ingestion", "processing", "storage", "serving"])
    score += 30 if coverage_hits == 4 else (18 if coverage_hits >= 2 else 0)
    if score >= 80:
        evidence.append("Architecture depth is strong.")
    return _bounded(score), evidence


def _score_kpi_specificity(sow: dict[str, Any]) -> tuple[int, list[str]]:
    evidence: list[str] = []
    score = 0
    metrics = ((sow.get("business_outcome") or {}).get("target_metrics") or [])
    metric_rows = 0
    measurable_rows = 0
    if isinstance(metrics, list):
        for row in metrics:
            row_txt = json.dumps(row or {}, ensure_ascii=True)
            if str((row or {}).get("metric") or "").strip():
                metric_rows += 1
            if len(re.findall(r"(\b\d+(\.\d+)?\b|%|>=|<=|<|>)", row_txt)) >= 1:
                measurable_rows += 1
    score += 25 if metric_rows >= 2 else (12 if metric_rows == 1 else 0)
    score += 20 if measurable_rows >= 2 else (10 if measurable_rows == 1 else 0)
    questions = ((sow.get("roi_dashboard_requirements") or {}).get("business_questions") or [])
    if isinstance(questions, list):
        score += 20 if len(questions) >= 3 else (10 if len(questions) >= 1 else 0)
    if score >= 75:
        evidence.append("KPI specificity is actionable.")
    return _bounded(score), evidence


def _score_interview_readiness(sow: dict[str, Any]) -> tuple[int, list[str]]:
    evidence: list[str] = []
    score = 0
    package = sow.get("interview_ready_package") or {}
    star_bullets = package.get("star_bullets") or []
    score += 30 if isinstance(star_bullets, list) and len(star_bullets) >= 4 else (18 if isinstance(star_bullets, list) and len(star_bullets) >= 2 else 0)
    checklist = package.get("portfolio_checklist") or []
    score += 25 if isinstance(checklist, list) and len(checklist) >= 3 else (12 if isinstance(checklist, list) and len(checklist) >= 1 else 0)
    if score >= 75:
        evidence.append("Interview readiness is strong.")
    return _bounded(score), evidence


def _metric_status(score: int) -> str:
    if score >= 85:
        return "pass"
    if score >= 70:
        return "partial"
    return "fail"


def _mk(metric_id: str, name: str, score: float, evidence: str, gap: str) -> dict[str, Any]:
    s = _bounded(score)
    return {
        "id": metric_id,
        "name": name,
        "score": s,
        "status": _metric_status(s),
        "weight": 10,
        "evidence": [evidence] if evidence else [],
        "gaps": [gap] if gap else [],
    }


def evaluate_sow_output(sow: dict[str, Any], reference_texts: list[str] | None = None) -> dict[str, Any]:
    text = _json_text(sow)
    milestones = sow.get("milestones") or []
    business = sow.get("business_outcome") or {}
    problem = str(business.get("problem_statement") or "")
    roi = sow.get("roi_dashboard_requirements") or {}
    role_scope = ((sow.get("candidate_profile") or {}).get("role_scope_assessment") or {})
    target_level = str(role_scope.get("target_role_level") or role_scope.get("current_role_level") or "mid").lower()

    required_top = ["project_title", "business_outcome", "solution_architecture", "project_story", "milestones", "roi_dashboard_requirements", "resource_plan", "project_charter"]
    top_hits = sum(1 for k in required_top if sow.get(k) not in (None, {}, [], ""))
    structural = _mk("structural_compliance", "Structural Compliance", (top_hits / 8.0) * 100.0, "Required SOW sections were checked.", "" if top_hits == 8 else "Missing required top-level sections.")

    realism_terms = ["abandon", "stockout", "margin", "revenue", "latency", "silo", "inventory", "returns", "retention", "risk"]
    realism_score = (35 if len(problem) >= 120 else (20 if len(problem) >= 70 else 0)) + min(65, _count_hits(text, realism_terms) * 8)
    realism = _mk("client_contextual_realism", "Client Contextual Realism", realism_score, "Scenario realism and pain-point detail were checked.", "" if realism_score >= 70 else "Business context is too generic.")

    business_why_hits = sum(1 for row in milestones if str((row or {}).get("business_why") or "").strip()) if isinstance(milestones, list) else 0
    golden_score = (business_why_hits / max(1, len(milestones))) * 60.0 if isinstance(milestones, list) and milestones else 0.0
    golden_score += min(40, _count_hits(text, ["kpi", "roi", "revenue", "margin", "retention", "cost"]) * 6)
    golden = _mk("golden_thread_mapping", "Golden Thread (Business-Technical Mapping)", golden_score, "Business-to-technical mapping was checked.", "" if golden_score >= 70 else "Milestones need stronger business mapping.")

    eco_hits = max(
        _count_hits(text, ["databricks", "unity catalog", "adls", "power bi"]),
        _count_hits(text, ["aws", "s3", "mwaa", "redshift"]),
        _count_hits(text, ["gcp", "bigquery", "gcs", "composer"]),
    )
    cohesion_score = min(100, (eco_hits * 20) + (_count_hits(text, ["delta", "lakehouse", "dbt", "spark", "semantic"]) * 8))
    cohesion = _mk("architectural_cohesion", "Architectural Cohesion", cohesion_score, "Enterprise stack cohesion was checked.", "" if cohesion_score >= 70 else "Stack looks under-specified or mixed.")

    ingestion_score = min(100, _count_hits(text, ["incremental", "oauth", "pagination", "cdc", "change data capture", "late-arriving", "stream", "micro-batch", "watermark", "upsert", "merge", "api polling"]) * 9)
    ingestion = _mk("ingestion_complexity", "Ingestion Complexity", ingestion_score, "Ingestion realism patterns were checked.", "" if ingestion_score >= 70 else "Ingestion patterns need more realistic complexity.")

    medallion_score = min(100, _count_hits(text, ["bronze", "silver", "gold"]) * 15 + _count_hits(text, ["fact", "dimension", "star schema", "kimball"]) * 12)
    medallion = _mk("medallion_layer_precision", "Medallion Layer Precision", medallion_score, "Medallion precision was checked.", "" if medallion_score >= 70 else "Medallion layer expectations need more precision.")

    resiliency_score = min(100, _count_hits(text, ["data quality", "dq", "expectation", "quarantine", "idempotent", "merge", "watermark", "audit", "logging", "batch_id", "rows_inserted"]) * 10)
    resiliency = _mk("enterprise_resiliency_mandates", "Enterprise Resiliency Mandates", resiliency_score, "Resiliency mandates were checked.", "" if resiliency_score >= 70 else "Explicit DQ/idempotency/observability mandates are weak.")

    roi_score = min(100, (len(roi.get("business_questions") or []) * 20) + _count_hits(_json_text(roi), ["risk", "opportunity", "threshold", "drill", "tooltip", "summary"]) * 8)
    roi_metric = _mk("roi_driven_servicing_requirements", "ROI-Driven Servicing Requirements", roi_score, "ROI and dashboard actionability were checked.", "" if roi_score >= 70 else "ROI/dashboard requirements are too generic.")

    effort_rows = ((((sow.get("project_charter") or {}).get("sections") or {}).get("implementation_plan") or {}).get("milestones") or [])
    effort_values = [float((row or {}).get("estimated_effort_hours")) for row in effort_rows if isinstance((row or {}).get("estimated_effort_hours"), (int, float))]
    in_band = sum(1 for val in effort_values if 5 <= val <= 15)
    milestone_score = (len(milestones) * 20) if isinstance(milestones, list) else 0
    milestone_score += (in_band / max(1, len(effort_values))) * 40 if effort_values else 0
    milestone_score += min(40, _count_hits(text, ["infrastructure", "bronze", "silver", "gold", "semantic", "bi", "dashboard"]) * 6)
    milestone_metric = _mk("milestone_estimation_and_dod", "Milestone Estimation and Definition of Done", milestone_score, "Milestone chunking and DoD were checked.", "" if milestone_score >= 70 else "Milestones need better chunking and acceptance criteria.")

    advanced_hits = _count_hits(text, ["ci/cd", "terraform", "iac", "liquid clustering", "streaming", "micro-batch", "unity catalog"])
    core_hits = _count_hits(text, ["sql", "pyspark", "data modeling", "dbt", "pipeline"])
    if target_level in {"senior", "staff", "principal", "lead"}:
        persona_score = min(100, (advanced_hits * 14) + (core_hits * 5))
    elif target_level in {"junior", "entry", "associate"}:
        persona_score = min(100, (core_hits * 12) + (advanced_hits * 4))
    else:
        persona_score = min(100, (core_hits * 8) + (advanced_hits * 8) + 10)
    persona = _mk("persona_calibration", "Persona Calibration", persona_score, "Persona-level calibration was checked.", "" if persona_score >= 70 else "Difficulty does not clearly match target persona.")

    meta_metrics = [structural, realism, golden, cohesion, ingestion, medallion, resiliency, roi_metric, milestone_metric, persona]
    meta_scores = [int(row["score"]) for row in meta_metrics]
    meta_overall = _bounded(sum(meta_scores) / max(1, len(meta_scores)))

    reference_alignment = {"score": None, "status": "no_references", "details": "No usable reference corpus provided.", "reference_count": 0}
    if reference_texts:
        ref_tokens = [tok for tok in re.findall(r"[a-z0-9]{3,}", " ".join(str(x or "").lower() for x in reference_texts))]
        sow_tokens = [tok for tok in re.findall(r"[a-z0-9]{3,}", text)]
        if ref_tokens and sow_tokens:
            high_signal = {tok for tok in ref_tokens if ref_tokens.count(tok) >= 3} or set(ref_tokens)
            overlap = len(high_signal.intersection(set(sow_tokens)))
            ref_score = _bounded((overlap / max(1, len(high_signal))) * 100.0)
            reference_alignment = {
                "score": ref_score,
                "status": "ok",
                "details": "Token overlap against high-signal reference corpus terms.",
                "reference_count": len(reference_texts),
                "high_signal_term_count": len(high_signal),
                "overlap_term_count": overlap,
            }

    overall_score = _bounded((0.9 * meta_overall) + (0.1 * int(reference_alignment["score"]))) if isinstance(reference_alignment.get("score"), int) else meta_overall
    meets_bar = overall_score >= 85 and min(meta_scores) >= 70 and sum(1 for row in meta_metrics if row["status"] in {"pass", "partial"}) >= 9

    legacy_scope, legacy_scope_ev = _score_scope_clarity(sow)
    legacy_arch, legacy_arch_ev = _score_architecture_depth(sow)
    legacy_kpi, legacy_kpi_ev = _score_kpi_specificity(sow)
    legacy_interview, legacy_interview_ev = _score_interview_readiness(sow)

    return {
        "rubric_version": RUBRIC_VERSION,
        "overall_score": overall_score,
        "meets_gold_standard_bar": meets_bar,
        "meta_rubric": {
            "rubric_name": "Gambill Data Project Generation Standards",
            "rubric_type": "generation_meta_rubric",
            "overall_score": meta_overall,
            "minimum_metric_score": min(meta_scores) if meta_scores else 0,
            "metrics": meta_metrics,
            "total_metrics": len(meta_metrics),
        },
        "categories": {
            "scope_clarity": {"score": legacy_scope, "evidence": legacy_scope_ev},
            "architecture_depth": {"score": legacy_arch, "evidence": legacy_arch_ev},
            "kpi_specificity": {"score": legacy_kpi, "evidence": legacy_kpi_ev},
            "interview_readiness": {"score": legacy_interview, "evidence": legacy_interview_ev},
        },
        "reference_alignment": reference_alignment,
        "summary": {
            "minimum_category_score": min([legacy_scope, legacy_arch, legacy_kpi, legacy_interview]),
            "score_band": "excellent" if overall_score >= 90 else ("strong" if overall_score >= 80 else ("fair" if overall_score >= 65 else "weak")),
        },
    }


def evaluate_sow_with_reference_paths(sow: dict[str, Any], reference_doc_paths: list[str] | None = None) -> dict[str, Any]:
    refs: list[str] = []
    path_meta: list[dict[str, Any]] = []
    for p in (reference_doc_paths or []):
        text, status = _load_reference_text(p)
        refs.append(text)
        path_meta.append({"path": str(p or ""), "status": status, "loaded_chars": len(text)})

    evaluation = evaluate_sow_output(sow, refs)
    evaluation["reference_documents"] = path_meta
    evaluation["reference_documents_loaded"] = sum(1 for row in path_meta if row["status"] == "ok")
    return evaluation
