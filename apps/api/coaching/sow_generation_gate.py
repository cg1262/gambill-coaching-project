from __future__ import annotations

import os
from typing import Any

from .sow_draft import build_sow_skeleton, generate_sow_with_llm as _base_generate_sow_with_llm
from .sow_evaluation import evaluate_sow_output

_ARCTYPE_ORDER = ["retail", "energy", "finance", "general"]


def _meta_rubric_threshold() -> int:
    raw = str(os.getenv("COACHING_META_RUBRIC_MIN_SCORE") or "85").strip()
    try:
        parsed = int(raw)
    except Exception:
        parsed = 85
    return max(50, min(99, parsed))


def _safe_score(evaluation: dict[str, Any] | None) -> int:
    try:
        return int((evaluation or {}).get("overall_score") or 0)
    except Exception:
        return 0


def _infer_archetype(strategy: dict[str, Any] | None, sow: dict[str, Any]) -> str:
    if isinstance(strategy, dict):
        archetype = str(strategy.get("archetype") or "").strip().lower()
        if archetype in set(_ARCTYPE_ORDER):
            return archetype

    text = str(sow or {}).lower()
    signals = {
        "retail": ["retail", "inventory", "store", "margin", "returns"],
        "energy": ["energy", "grid", "ev", "charging", "telemetry"],
        "finance": ["finance", "market", "crypto", "trading", "liquidation"],
    }
    best = "general"
    best_score = -1
    for name, terms in signals.items():
        score = sum(1 for term in terms if term in text)
        if score > best_score:
            best = name
            best_score = score
    return best


def _alternate_archetypes(primary: str) -> list[str]:
    normalized = str(primary or "").strip().lower()
    return [name for name in _ARCTYPE_ORDER if name != normalized]


def generate_sow_with_llm(
    intake: dict[str, Any],
    parsed_jobs: list[dict[str, Any]],
    timeout: int = 45,
    max_retries: int = 2,
) -> dict[str, Any]:
    result = _base_generate_sow_with_llm(
        intake=intake,
        parsed_jobs=parsed_jobs,
        timeout=timeout,
        max_retries=max_retries,
    )

    original_sow = result.get("sow") or build_sow_skeleton(intake=intake, parsed_jobs=parsed_jobs)
    threshold = _meta_rubric_threshold()
    initial_eval = evaluate_sow_output(original_sow)
    initial_score = _safe_score(initial_eval)

    llm_meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    strategy = (((llm_meta or {}).get("strategy") or {}).get("project_strategy") or {})
    if not isinstance(strategy, dict):
        strategy = {}

    best_sow = original_sow
    best_eval = initial_eval
    best_score = initial_score
    selected_archetype = _infer_archetype(strategy, original_sow)
    attempts: list[dict[str, Any]] = []

    if initial_score < threshold:
        for archetype in _alternate_archetypes(selected_archetype):
            strategy_override = dict(strategy)
            strategy_override["archetype"] = archetype
            candidate = build_sow_skeleton(
                intake=intake,
                parsed_jobs=parsed_jobs,
                project_strategy=strategy_override,
            )
            candidate_eval = evaluate_sow_output(candidate)
            candidate_score = _safe_score(candidate_eval)
            attempts.append({"archetype": archetype, "overall_score": candidate_score})
            if candidate_score > best_score:
                best_sow = candidate
                best_eval = candidate_eval
                best_score = candidate_score
                selected_archetype = archetype
            if best_score >= threshold:
                break

    gate_status = "initial_pass"
    if initial_score < threshold:
        if best_score >= threshold and best_sow is not original_sow:
            gate_status = "reprocessed_pass"
        elif best_sow is not original_sow:
            gate_status = "reprocessed_best_effort_below_threshold"
        else:
            gate_status = "below_threshold_no_improvement"

    gate = {
        "threshold": threshold,
        "initial_overall_score": initial_score,
        "final_overall_score": best_score,
        "met_threshold_initially": initial_score >= threshold,
        "met_threshold_final": best_score >= threshold,
        "reprocessed": best_sow is not original_sow,
        "reprocess_attempts": attempts,
        "selected_archetype": selected_archetype,
        "status": gate_status,
    }

    merged_meta = dict(llm_meta or {})
    merged_meta["meta_rubric_gate"] = gate
    merged_meta["meta_rubric_evaluation"] = best_eval

    return {
        **result,
        "sow": best_sow,
        "meta": merged_meta,
    }
