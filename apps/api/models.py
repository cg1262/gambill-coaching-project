from __future__ import annotations
from datetime import datetime, timezone
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class Position(BaseModel):
    x: float
    y: float


class ColumnDef(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    data_type: Literal["string", "int", "bigint", "decimal", "boolean", "date", "timestamp", "json", "array", "struct"] = Field(
        validation_alias=AliasChoices("data_type", "dataType")
    )
    nullable: bool = True
    is_primary_key: bool = Field(default=False, validation_alias=AliasChoices("is_primary_key", "isPrimaryKey"))
    description: str | None = None
    tags: list[str] = Field(default_factory=list)


class TableNode(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    catalog: str | None = None
    schema: str
    table: str
    description: str | None = None
    columns: list[ColumnDef]
    position: Position
    source: Literal["mock", "unity_catalog"]


class RelationshipJoin(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_column: str = Field(validation_alias=AliasChoices("from_column", "fromColumn"))
    to_column: str = Field(validation_alias=AliasChoices("to_column", "toColumn"))


class RelationshipEdge(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    from_table_id: str = Field(validation_alias=AliasChoices("from_table_id", "fromTableId"))
    to_table_id: str = Field(validation_alias=AliasChoices("to_table_id", "toTableId"))
    from_column: str = Field(default="id", validation_alias=AliasChoices("from_column", "fromColumn"))
    to_column: str = Field(default="id", validation_alias=AliasChoices("to_column", "toColumn"))
    join_columns: list[RelationshipJoin] = Field(default_factory=list, validation_alias=AliasChoices("join_columns", "joinColumns"))
    relationship_type: Literal["one_to_one", "one_to_many", "many_to_one", "many_to_many"] = Field(
        validation_alias=AliasChoices("relationship_type", "relationshipType")
    )


class CanvasAST(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: Literal["1.0"] = "1.0"
    workspace_id: str = Field(validation_alias=AliasChoices("workspace_id", "workspaceId"))
    tables: list[TableNode]
    relationships: list[RelationshipEdge] = Field(default_factory=list)
    modified_table_ids: list[str] = Field(default_factory=list, validation_alias=AliasChoices("modified_table_ids", "modifiedTableIds"))


class Violation(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    code: str
    severity: Literal["HIGH", "MED", "LOW"]
    message: str
    table_id: str | None = Field(default=None, validation_alias=AliasChoices("table_id", "tableId"))
    column_name: str | None = Field(default=None, validation_alias=AliasChoices("column_name", "columnName"))
    source: Literal["deterministic", "probabilistic"]
    confidence: float | None = None


class ValidationResult(BaseModel):
    violations: list[Violation]
    checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Dependency(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    object_name: str = Field(validation_alias=AliasChoices("object_name", "objectName"))
    dependency_type: Literal["table", "view", "pipeline", "code_ref"] = Field(
        validation_alias=AliasChoices("dependency_type", "dependencyType")
    )
    source: Literal["deterministic", "probabilistic"]
    confidence: float
    color: Literal["red", "yellow", "green"]


class ImpactResult(BaseModel):
    dependencies: list[Dependency]
    checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class SowMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str
    duration_weeks: int = Field(ge=1, validation_alias=AliasChoices("duration_weeks", "durationWeeks"))
    deliverables: list[str] = Field(default_factory=list)
    milestone_tags: list[str] = Field(default_factory=list, validation_alias=AliasChoices("milestone_tags", "milestoneTags"))
    resources: list[dict] = Field(default_factory=list)
    execution_plan: str = Field(default="", validation_alias=AliasChoices("execution_plan", "executionPlan"))
    expected_deliverable: str = Field(default="", validation_alias=AliasChoices("expected_deliverable", "expectedDeliverable"))
    business_why: str = Field(default="", validation_alias=AliasChoices("business_why", "businessWhy"))
    acceptance_checks: list[str] = Field(default_factory=list, validation_alias=AliasChoices("acceptance_checks", "acceptanceChecks"))


class CoachingSowDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: str = "0.2"
    project_title: str
    candidate_profile: dict = Field(default_factory=dict)
    business_outcome: dict
    solution_architecture: dict
    project_story: dict
    milestones: list[SowMilestone]
    roi_dashboard_requirements: dict = Field(validation_alias=AliasChoices("roi_dashboard_requirements", "roiDashboardRequirements"))
    resource_plan: dict = Field(validation_alias=AliasChoices("resource_plan", "resourcePlan"))
    mentoring_cta: dict = Field(validation_alias=AliasChoices("mentoring_cta", "mentoringCta"))
    project_charter: dict = Field(default_factory=dict, validation_alias=AliasChoices("project_charter", "projectCharter"))
    interview_ready_package: dict = Field(default_factory=dict, validation_alias=AliasChoices("interview_ready_package", "interviewReadyPackage"))
