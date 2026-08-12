from __future__ import annotations

from uuid import uuid4

from sympy import Eq, Rational, Symbol

from .geometry_kernel import GeometryKernel
from .geometry_models import (
    DiagramPatch,
    FactStatus,
    GeometryFact,
    TraceNode,
    ValidateSplitRequest,
    ValidateSplitResponse,
)


class GeometryReasoner:
    def __init__(self, kernel: GeometryKernel | None = None):
        self.kernel = kernel or GeometryKernel()

    def validate_rectangle_partition(self, request: ValidateSplitRequest) -> ValidateSplitResponse:
        operation = self.kernel.split_region(
            request.original_region_id,
            request.original_region,
            request.splitter_id,
            request.splitter,
            request.tolerance,
        )
        base_facts: list[GeometryFact] = []

        if operation.status != "valid":
            return ValidateSplitResponse(
                operation=operation,
                facts=base_facts,
                algebraic_constraints=[],
                verification_trace=[TraceNode(
                    trace_id=str(uuid4()),
                    rule_id="split_region_by_segment",
                    input_fact_ids=[],
                    status="failed",
                    details={"reason": operation.reason, "checks": [item.model_dump() for item in operation.checks]},
                )],
                diagram_patch=self._patch(request, operation, False),
            )

        if len(operation.output_entities) != len(request.part_dimensions):
            operation.status = "incomplete"
            operation.reason = "分割区域数量与提供的尺寸数量不一致"
            return ValidateSplitResponse(
                operation=operation,
                facts=base_facts,
                algebraic_constraints=[],
                verification_trace=[TraceNode(
                    trace_id=str(uuid4()),
                    rule_id="rectangle_area_partition",
                    input_fact_ids=[],
                    status="not_run",
                    details={"reason": operation.reason},
                )],
                diagram_patch=self._patch(request, operation, False),
            )

        facts = list(base_facts)
        constraints = []
        trace_nodes = []
        area_symbols = []
        result_values = []

        for index, (region_id, dimensions) in enumerate(
            zip(operation.output_entities, request.part_dimensions, strict=True),
            start=1,
        ):
            facts.append(self._fact(
                request,
                f"fact_rectangle_{index}",
                "is_rectangle",
                [region_id],
                FactStatus.CONFIRMED_STUDENT,
                "student_confirmed_part_shape",
            ))
            width = Rational(str(dimensions.width.value))
            height = Rational(str(dimensions.height.value))
            area_symbol = Symbol(f"area_{region_id}", positive=True)
            visible_constraint = (
                f"Eq({area_symbol}, {width} * {height})"
            )
            area_symbols.append(area_symbol)
            result_values.append(width * height)
            constraints.append(visible_constraint)
            derived_fact = self._fact(
                request,
                f"fact_area_{index}",
                "area",
                [region_id],
                FactStatus.DERIVED_VERIFIED,
                "geometry_rule",
                value={
                    "number": float(width * height),
                    "unit": f"{dimensions.width.unit}²",
                },
            )
            facts.append(derived_fact)
            trace_nodes.append(TraceNode(
                trace_id=str(uuid4()),
                rule_id="rectangle_area",
                input_fact_ids=[f"fact_rectangle_{index}"],
                output_fact_ids=[derived_fact.fact_id],
                produced_constraints=[visible_constraint],
                status="verified",
                details={
                    "region_id": region_id,
                    "width": str(width),
                    "height": str(height),
                    "unit": dimensions.width.unit,
                },
            ))

        total_symbol = Symbol(f"area_{request.original_region_id}", positive=True)
        total_equation = Eq(total_symbol, sum(area_symbols))
        constraints.append(str(total_equation))
        total_value = sum(result_values)
        total_fact = self._fact(
            request,
            "fact_area_total",
            "area",
            [request.original_region_id],
            FactStatus.DERIVED_VERIFIED,
            "geometry_rule",
            value={"number": float(total_value), "unit": f"{request.part_dimensions[0].width.unit}²"},
        )
        partition_fact = self._fact(
            request,
            "fact_partition",
            "disjoint_union",
            [request.original_region_id, *operation.output_entities],
            FactStatus.DERIVED_VERIFIED,
            "geometry_kernel",
        )
        facts.append(partition_fact)
        facts.append(total_fact)
        trace_nodes.append(TraceNode(
            trace_id=str(uuid4()),
            rule_id="disjoint_area_sum",
            input_fact_ids=[
                "fact_partition",
                *[f"fact_area_{index}" for index in range(1, len(result_values) + 1)],
            ],
            output_fact_ids=[total_fact.fact_id],
            produced_constraints=[str(total_equation)],
            status="verified",
            details={
                "coverage_check": "union_matches_original",
                "overlap_check": "output_regions_disjoint",
            },
        ))

        return ValidateSplitResponse(
            operation=operation,
            facts=facts,
            algebraic_constraints=constraints,
            result_summary=f"辅助线形成 {len(result_values)} 个有效长方形区域，面积可以由各部分相加得到；具体计算留给学生完成",
            verification_trace=trace_nodes,
            diagram_patch=self._patch(request, operation, True),
        )

    @staticmethod
    def _fact(
        request: ValidateSplitRequest,
        fact_id: str,
        predicate: str,
        subjects: list[str],
        status: FactStatus,
        source: str,
        value: dict | None = None,
    ) -> GeometryFact:
        return GeometryFact(
            fact_id=fact_id,
            predicate=predicate,
            subjects=subjects,
            status=status,
            source=source,
            value=value,
            problem_version=request.problem_version,
            diagram_version=request.diagram_version,
        )

    @staticmethod
    def _patch(request: ValidateSplitRequest, operation, valid: bool) -> DiagramPatch:
        regions = [
            {
                "entity_id": entity_id,
                "type": "region",
                "points": [point.model_dump() for point in region.points],
                "state": "verified" if valid else "candidate",
            }
            for entity_id, region in zip(
                operation.output_entities,
                operation.output_regions,
                strict=False,
            )
        ]
        return DiagramPatch(
            diagram_version=request.diagram_version,
            focus_entities=operation.output_entities if valid else [request.splitter_id],
            add_helper_entities=[{
                "entity_id": request.splitter_id,
                "type": "segment",
                "origin": "helper",
                "style": "dashed",
                "start": request.splitter.start.model_dump(),
                "end": request.splitter.end.model_dump(),
                "state": "verified" if valid else "invalid",
            }],
            add_regions=regions,
            caption=(
                "这条辅助线形成了完整且互不重叠的区域。"
                if valid else "这条辅助线还没有形成可验证的完整分割。"
            ),
        )
