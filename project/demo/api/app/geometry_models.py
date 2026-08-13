from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Point2D(BaseModel):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)


class PolygonGeometry(BaseModel):
    points: list[Point2D] = Field(min_length=3, max_length=64)


class SegmentGeometry(BaseModel):
    start: Point2D
    end: Point2D

    @model_validator(mode="after")
    def endpoints_are_distinct(self):
        if self.start == self.end:
            raise ValueError("辅助线的两个端点不能相同")
        return self


class ToleranceProfile(BaseModel):
    profile_id: str = "photo_diagram_v1"
    point_merge_ratio: float = 0.008
    boundary_snap_ratio: float = 0.01
    collinear_angle_degrees: float = 2.0
    coverage_area_ratio: float = 0.005
    overlap_area_ratio: float = 0.002
    fragment_area_ratio: float = 0.002


class Quantity(BaseModel):
    value: float = Field(gt=0)
    unit: str = "cm"


class RectangleDimensions(BaseModel):
    width: Quantity
    height: Quantity

    @model_validator(mode="after")
    def units_match(self):
        if self.width.unit != self.height.unit:
            raise ValueError("长和宽必须使用相同单位")
        return self


class FactStatus(StrEnum):
    CANDIDATE = "candidate"
    CONFIRMED_SOURCE = "confirmed_source"
    CONFIRMED_STUDENT = "confirmed_student"
    DERIVED_VERIFIED = "derived_verified"
    REJECTED = "rejected"
    INVALIDATED = "invalidated"


class StandardPredicate(StrEnum):
    IS_TRIANGLE = "is_triangle"
    IS_RECTANGLE = "is_rectangle"
    IS_SQUARE = "is_square"
    IS_PARALLELOGRAM = "is_parallelogram"
    IS_TRAPEZOID = "is_trapezoid"
    IS_CIRCLE = "is_circle"
    IS_SEMICIRCLE = "is_semicircle"
    IS_SECTOR = "is_sector"
    ENDPOINT_OF = "endpoint_of"
    BOUNDARY_EDGE = "boundary_edge"
    INSIDE = "inside"
    CONTAINS = "contains"
    INTERSECTS = "intersects"
    DISJOINT = "disjoint"
    OVERLAPS = "overlaps"
    COMPOSED_OF = "composed_of"
    PARALLEL = "parallel"
    PERPENDICULAR = "perpendicular"
    EQUAL_LENGTH = "equal_length"
    COLLINEAR = "collinear"
    TANGENT = "tangent"
    ADJACENT = "adjacent"
    SHARES_BOUNDARY = "shares_boundary"
    LENGTH = "length"
    ANGLE_MEASURE = "angle_measure"
    RADIUS = "radius"
    DIAMETER = "diameter"
    PERIMETER = "perimeter"
    AREA = "area"
    DISJOINT_UNION = "disjoint_union"
    REGION_DIFFERENCE = "region_difference"
    EQUAL_AREA = "equal_area"
    SPLIT_INTO = "split_into"
    REARRANGED_TO = "rearranged_to"


class GeometryFact(BaseModel):
    fact_id: str
    predicate: StandardPredicate
    subjects: list[str]
    status: FactStatus
    source: str
    value: dict | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    problem_version: int = Field(ge=1)
    diagram_version: int = Field(ge=1)


class GeometryCheck(BaseModel):
    check: str
    passed: bool
    detail: str
    measured_value: float | None = None
    allowed_value: float | None = None


class GeometryOperationResult(BaseModel):
    operation: str
    status: Literal[
        "valid", "invalid", "incomplete", "underdetermined",
        "unsupported", "uncertain", "conflicts_with_problem",
    ]
    input_entities: list[str]
    output_entities: list[str] = Field(default_factory=list)
    output_regions: list[PolygonGeometry] = Field(default_factory=list)
    checks: list[GeometryCheck] = Field(default_factory=list)
    tolerance_profile: str
    geometry_engine: str = "shapely"
    geometry_engine_version: str
    reason: str | None = None


class TraceNode(BaseModel):
    trace_id: str
    rule_id: str
    input_fact_ids: list[str]
    output_fact_ids: list[str] = Field(default_factory=list)
    produced_constraints: list[str] = Field(default_factory=list)
    status: Literal["verified", "failed", "not_run"]
    details: dict = Field(default_factory=dict)


class DiagramPatch(BaseModel):
    diagram_version: int
    focus_entities: list[str] = Field(default_factory=list)
    add_helper_entities: list[dict] = Field(default_factory=list)
    add_regions: list[dict] = Field(default_factory=list)
    caption: str


class DiagramEntityDraft(BaseModel):
    entity_id: str
    type: Literal["point", "segment", "circle", "arc", "polygon", "region", "text_label", "measurement_label", "symbol_marker"]
    label: str | None = None
    geometry: dict = Field(default_factory=dict)
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Literal["candidate", "needs_confirmation", "confirmed"] = "candidate"


class DiagramRelationDraft(BaseModel):
    relation_id: str
    predicate: StandardPredicate
    subjects: list[str] = Field(min_length=1)
    value: dict | None = None
    source: Literal["problem_text", "explicit_diagram_mark", "model_inferred"]
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Literal["candidate", "needs_confirmation", "confirmed"] = "candidate"

    @field_validator("value", mode="before")
    @classmethod
    def normalize_model_value(cls, value: Any) -> dict | None:
        """Tolerate common multimodal-model scalar output at the API boundary."""
        if value is None or isinstance(value, dict):
            return value
        if isinstance(value, (str, int, float, bool)):
            return {"raw": value}
        if isinstance(value, list):
            return {"items": value}
        raise ValueError("关系 value 必须是对象、标量、数组或 null")


class DiagramUncertainty(BaseModel):
    uncertainty_id: str
    description: str
    affected_entity_ids: list[str] = Field(default_factory=list)
    candidates: list[str] = Field(default_factory=list)
    requires_confirmation: bool = True


class DiagramGraphDraft(BaseModel):
    schema_version: str = "1.0"
    diagram_id: str
    diagram_type: Literal["geometry", "segment_model", "motion", "statistics", "other"]
    source_diagram_type: str | None = None
    entities: list[DiagramEntityDraft] = Field(default_factory=list, max_length=100)
    relations: list[DiagramRelationDraft] = Field(default_factory=list, max_length=100)
    uncertainties: list[DiagramUncertainty] = Field(default_factory=list, max_length=30)
    confidence: float = Field(default=0.5, ge=0, le=1)
    status: Literal["draft", "confirmed"] = "draft"

    @model_validator(mode="before")
    @classmethod
    def normalize_diagram_type(cls, value):
        if not isinstance(value, dict):
            return value
        data = dict(value)
        raw_type = data.get("diagram_type", "other")
        if not isinstance(raw_type, str):
            data["source_diagram_type"] = str(raw_type)
            data["diagram_type"] = "other"
            return data
        normalized = raw_type.strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "grid": "geometry",
            "shape": "geometry",
            "geometric": "geometry",
            "geometry_diagram": "geometry",
            "composite_shape": "geometry",
            "area_diagram": "geometry",
            "line_segment": "segment_model",
            "bar_model": "segment_model",
            "tape_diagram": "segment_model",
            "travel": "motion",
            "route": "motion",
            "chart": "statistics",
            "graph": "statistics",
            "table": "statistics",
        }
        allowed = {"geometry", "segment_model", "motion", "statistics", "other"}
        canonical = aliases.get(normalized, normalized if normalized in allowed else "other")
        if canonical != normalized:
            data["source_diagram_type"] = raw_type
        data["diagram_type"] = canonical
        return data


class ValidateSplitRequest(BaseModel):
    problem_version: int = Field(default=1, ge=1)
    diagram_version: int = Field(default=1, ge=1)
    original_region_id: str = "region_shaded"
    original_region: PolygonGeometry
    splitter_id: str = "helper_split_1"
    splitter: SegmentGeometry
    expected_part_shape: Literal["rectangle"] = "rectangle"
    part_dimensions: list[RectangleDimensions] = Field(min_length=2, max_length=3)
    tolerance: ToleranceProfile = Field(default_factory=ToleranceProfile)


class ValidateSplitResponse(BaseModel):
    operation: GeometryOperationResult
    facts: list[GeometryFact]
    algebraic_constraints: list[str]
    result_summary: str | None = None
    verification_trace: list[TraceNode]
    diagram_patch: DiagramPatch
