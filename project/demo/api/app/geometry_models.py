from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


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
