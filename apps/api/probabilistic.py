from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, ValidationError


class ProbabilisticFinding(BaseModel):
    object_name: str
    dependency_type: Literal["table", "view", "pipeline", "code_ref"]
    confidence: float = Field(ge=0, le=100)
    rationale: str


def confidence_to_color(confidence: float) -> Literal["red", "yellow", "green"]:
    if confidence >= 95:
        return "green"
    if confidence >= 85:
        return "yellow"
    return "red"


def gate_findings(raw_findings: list[dict], min_confidence: float = 80.0) -> list[ProbabilisticFinding]:
    approved: list[ProbabilisticFinding] = []
    for f in raw_findings:
        try:
            parsed = ProbabilisticFinding.model_validate(f)
        except ValidationError:
            continue
        if parsed.confidence >= min_confidence:
            approved.append(parsed)
    return approved
