import pytest
from pydantic import ValidationError

from app.geometry_models import (
    DiagramGraphDraft,
    FactStatus,
    GeometryFact,
    Point2D,
    PolygonGeometry,
    Quantity,
    RectangleDimensions,
    SegmentGeometry,
    ValidateSplitRequest,
)
from app.geometry_rules import GeometryReasoner


def _rectangle() -> PolygonGeometry:
    return PolygonGeometry(points=[
        Point2D(x=0.1, y=0.1),
        Point2D(x=0.9, y=0.1),
        Point2D(x=0.9, y=0.9),
        Point2D(x=0.1, y=0.9),
    ])


def _dimensions(width: float, height: float) -> RectangleDimensions:
    return RectangleDimensions(
        width=Quantity(value=width, unit="cm"),
        height=Quantity(value=height, unit="cm"),
    )


def test_valid_helper_line_creates_verified_partition_and_area_trace():
    request = ValidateSplitRequest(
        original_region=_rectangle(),
        splitter=SegmentGeometry(
            start=Point2D(x=0.5, y=0.1),
            end=Point2D(x=0.5, y=0.9),
        ),
        part_dimensions=[_dimensions(4, 8), _dimensions(4, 8)],
    )

    response = GeometryReasoner().validate_rectangle_partition(request)

    assert response.operation.status == "valid"
    assert len(response.operation.output_regions) == 2
    assert all(check.passed for check in response.operation.checks)
    assert any(fact.predicate == "disjoint_union" for fact in response.facts)
    assert any(fact.predicate == "area" and fact.value["number"] == 64 for fact in response.facts)
    assert len(response.algebraic_constraints) == 3
    assert response.verification_trace[-1].rule_id == "disjoint_area_sum"
    assert response.diagram_patch.focus_entities == ["region_shaded_part_1", "region_shaded_part_2"]


def test_helper_line_inside_region_is_rejected_without_area_reasoning():
    request = ValidateSplitRequest(
        original_region=_rectangle(),
        splitter=SegmentGeometry(
            start=Point2D(x=0.5, y=0.2),
            end=Point2D(x=0.5, y=0.8),
        ),
        part_dimensions=[_dimensions(4, 8), _dimensions(4, 8)],
    )

    response = GeometryReasoner().validate_rectangle_partition(request)

    assert response.operation.status == "invalid"
    assert response.algebraic_constraints == []
    assert response.verification_trace[0].status == "failed"
    assert response.diagram_patch.focus_entities == ["helper_split_1"]


def test_dimension_count_must_match_created_regions():
    request = ValidateSplitRequest(
        original_region=_rectangle(),
        splitter=SegmentGeometry(
            start=Point2D(x=0.5, y=0.1),
            end=Point2D(x=0.5, y=0.9),
        ),
        part_dimensions=[_dimensions(4, 8), _dimensions(2, 8), _dimensions(2, 8)],
    )

    response = GeometryReasoner().validate_rectangle_partition(request)

    assert response.operation.status == "incomplete"
    assert response.algebraic_constraints == []
    assert response.verification_trace[0].status == "not_run"


def test_geometry_fact_rejects_non_standard_predicate():
    with pytest.raises(ValidationError):
        GeometryFact(
            fact_id="free-form",
            predicate="looks_like_rectangle",
            subjects=["region_1"],
            status=FactStatus.CANDIDATE,
            source="vision_model",
            problem_version=1,
            diagram_version=1,
        )


def test_diagram_graph_draft_accepts_controlled_entities_and_relations():
    graph = DiagramGraphDraft.model_validate({
        "diagram_id": "diagram-1",
        "diagram_type": "geometry",
        "confidence": 0.91,
        "entities": [
            {"entity_id": "region_1", "type": "region", "geometry": {"points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9]]}, "confidence": 0.9},
            {"entity_id": "seg_1", "type": "segment", "geometry": {"start": [0.1, 0.1], "end": [0.9, 0.1]}, "confidence": 0.92},
        ],
        "relations": [{
            "relation_id": "rel_1", "predicate": "boundary_edge", "subjects": ["region_1", "seg_1"],
            "source": "model_inferred", "confidence": 0.8, "status": "needs_confirmation",
        }],
        "uncertainties": [{"uncertainty_id": "u1", "description": "边界绑定需要确认", "affected_entity_ids": ["seg_1"]}],
    })
    assert graph.status == "draft"
    assert graph.relations[0].predicate == "boundary_edge"


def test_diagram_graph_draft_normalizes_scalar_relation_value_from_vision_model():
    graph = DiagramGraphDraft.model_validate({
        "diagram_id": "diagram_scalar_value",
        "diagram_type": "geometry",
        "relations": [{
            "relation_id": "relation_grid",
            "predicate": "composed_of",
            "subjects": ["region_1"],
            "value": "grid",
            "source": "model_inferred",
            "confidence": 0.72,
            "status": "needs_confirmation",
        }],
    })

    assert graph.relations[0].value == {"raw": "grid"}


def test_diagram_graph_draft_normalizes_grid_diagram_type():
    graph = DiagramGraphDraft.model_validate({
        "diagram_id": "diagram_grid",
        "diagram_type": "grid",
    })

    assert graph.diagram_type == "geometry"
    assert graph.source_diagram_type == "grid"


def test_diagram_graph_draft_degrades_unknown_diagram_type_to_other():
    graph = DiagramGraphDraft.model_validate({
        "diagram_id": "diagram_unknown",
        "diagram_type": "unexpected_model_label",
    })

    assert graph.diagram_type == "other"
    assert graph.source_diagram_type == "unexpected_model_label"
