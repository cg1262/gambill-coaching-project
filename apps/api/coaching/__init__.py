from __future__ import annotations

# Re-exports - keeps "from coaching import X" working in main.py unchanged.

from .constants import (
    COMMON_SKILLS,
    COMMON_DOMAINS,
    COMMON_TOOLS,
    TAG_TOPIC_MAP,
    REQUIRED_SECTION_FLOW,
    CHARTER_REQUIRED_SECTION_FLOW,
    DATA_SOURCE_CANDIDATES,
    RESUME_TOOL_KEYWORDS,
    RESUME_DOMAIN_KEYWORDS,
    RESUME_PROJECT_KEYWORDS,
    STYLE_ANCHORS,
)
from .sow_security import sanitize_generated_sow, utc_now_iso
from .intake import fetch_job_text, extract_job_signals, extract_resume_signals
from .sow_draft import build_sow_skeleton
from .sow_generation_gate import generate_sow_with_llm
from .sow_validation import (
    validate_sow_payload,
    compute_sow_quality_score,
    build_quality_diagnostics,
    ensure_interview_ready_package,
    enforce_required_section_order,
    evaluate_sow_structure,
)
from .sow_completion import (
    auto_revise_sow_once,
    match_resources_for_sow,
    compose_demo_project_package,
)
from .sow_evaluation import (
    evaluate_sow_output,
    evaluate_sow_with_reference_paths,
)

__all__ = [
    "fetch_job_text",
    "extract_job_signals",
    "extract_resume_signals",
    "build_sow_skeleton",
    "generate_sow_with_llm",
    "validate_sow_payload",
    "auto_revise_sow_once",
    "match_resources_for_sow",
    "compose_demo_project_package",
    "sanitize_generated_sow",
    "compute_sow_quality_score",
    "build_quality_diagnostics",
    "ensure_interview_ready_package",
    "enforce_required_section_order",
    "evaluate_sow_structure",
    "evaluate_sow_output",
    "evaluate_sow_with_reference_paths",
    "utc_now_iso",
    "COMMON_SKILLS",
    "COMMON_DOMAINS",
    "COMMON_TOOLS",
    "TAG_TOPIC_MAP",
    "REQUIRED_SECTION_FLOW",
    "CHARTER_REQUIRED_SECTION_FLOW",
    "DATA_SOURCE_CANDIDATES",
    "RESUME_TOOL_KEYWORDS",
    "RESUME_DOMAIN_KEYWORDS",
    "RESUME_PROJECT_KEYWORDS",
    "STYLE_ANCHORS",
]
