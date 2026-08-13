from __future__ import annotations

from dataclasses import dataclass, field
from fractions import Fraction
from typing import Any

from sympy import Eq, Rational, Symbol, simplify

from .geometry_models import DiagramGraphDraft


@dataclass
class DiagramSolveResult:
    status: str
    facts: list[dict[str, Any]] = field(default_factory=list)
    constraints: list[dict[str, str]] = field(default_factory=list)
    answer: dict[str, Any] | None = None
    solution_steps: list[dict[str, Any]] = field(default_factory=list)
    core_understandings: list[str] = field(default_factory=list)
    verification_trace: list[dict[str, Any]] = field(default_factory=list)
    missing_facts: list[str] = field(default_factory=list)


class DiagramGraphSolver:
    """Convert confirmed diagram facts into a small, deterministic area model."""

    def solve(self, graph_data: dict[str, Any] | None) -> DiagramSolveResult:
        if not graph_data:
            return DiagramSolveResult(status="not_applicable")
        graph = DiagramGraphDraft.model_validate(graph_data)
        if graph.status != "confirmed":
            return DiagramSolveResult(status="needs_confirmation", missing_facts=["图形尚未确认"])
        result = self._solve_grid_polygon(graph)
        if result.status != "unsupported":
            return result
        return DiagramSolveResult(
            status="unsupported",
            missing_facts=["当前几何内核尚未找到可验证的面积规则和完整尺寸绑定"],
        )

    def _solve_grid_polygon(self, graph: DiagramGraphDraft) -> DiagramSolveResult:
        grid = self._find_grid_metadata(graph)
        polygon = next((entity for entity in graph.entities if entity.type == "polygon" and self._vertices(entity.geometry)), None)
        if polygon is None:
            polygon = next(
                (entity for entity in graph.entities if entity.type == "region" and self._vertices(entity.geometry) and not self._has_grid_metadata(entity.geometry)),
                None,
            )
        if grid is None and polygon is None:
            return DiagramSolveResult(status="unsupported")
        missing = []
        if grid is None:
            missing.append("缺少网格行列数或单格面积")
        if polygon is None:
            missing.append("缺少目标区域的多边形顶点")
        if missing:
            return DiagramSolveResult(status="insufficient_facts", missing_facts=missing)

        columns, rows, cell_area, unit = grid
        vertices = self._vertices(polygon.geometry)
        assert vertices is not None
        coordinate_space = polygon.geometry.get("coordinate_space")
        if coordinate_space == "grid" or polygon.geometry.get("grid_vertices"):
            points = polygon.geometry.get("grid_vertices", vertices)
        elif coordinate_space == "normalized" or all(0 <= p[0] <= 1 and 0 <= p[1] <= 1 for p in vertices):
            return DiagramSolveResult(
                status="insufficient_facts",
                missing_facts=["目标区域只有整张图片的归一化坐标，缺少相对于网格原点的格点坐标"],
            )
        else:
            points = vertices
        area_in_cells = self._shoelace(points)
        if area_in_cells <= 0:
            return DiagramSolveResult(status="invalid", missing_facts=["目标区域顶点不能形成有效面积"])
        area_value = area_in_cells * cell_area
        area_symbol = Symbol("target_area", positive=True)
        equation = Eq(area_symbol, Rational(area_in_cells.numerator, area_in_cells.denominator) * Rational(cell_area.numerator, cell_area.denominator))
        passed = simplify(equation.lhs.subs({area_symbol: Rational(area_value.numerator, area_value.denominator)}) - equation.rhs) == 0
        facts = [
            {"predicate": "grid_size", "subjects": [graph.diagram_id], "value": {"columns": columns, "rows": rows}, "status": "confirmed_student"},
            {"predicate": "cell_area", "subjects": [graph.diagram_id], "value": {"number": self._public(cell_area), "unit": unit}, "status": "confirmed_student"},
            {"predicate": "polygon_vertices", "subjects": [polygon.entity_id], "value": {"grid_points": points}, "status": "confirmed_student"},
            {"predicate": "area", "subjects": [polygon.entity_id], "value": {"number": self._public(area_value), "unit": unit}, "status": "derived_verified"},
        ]
        return DiagramSolveResult(
            status="verified" if passed else "invalid",
            facts=facts,
            constraints=[{"left": "target_area", "right": str(equation.rhs), "source_text": "网格多边形面积约束"}],
            answer={"target_area": self._public(area_value)},
            solution_steps=[
                {"goal": "把目标区域的顶点对应到网格交点", "operation": "读取已确认的格点坐标", "expression": None},
                {"goal": "求多边形覆盖的方格面积", "operation": "使用鞋带公式，或等价地分割/补形", "expression": f"target_area={equation.rhs}"},
                {"goal": "结合每个小方格的面积", "operation": "方格数乘单格面积", "expression": f"target_area={self._public(area_value)}"},
            ],
            core_understandings=["网格题的坐标单位是小方格边长", "不规则多边形可以用分割、补形或鞋带公式验证面积"],
            verification_trace=[{
                "rule_id": "grid_polygon_shoelace_area",
                "status": "verified" if passed else "failed",
                "input_entity_ids": [graph.diagram_id, polygon.entity_id],
                "produced_constraint": str(equation),
                "substitution_passed": bool(passed),
            }],
        )

    @staticmethod
    def _find_grid_metadata(graph: DiagramGraphDraft) -> tuple[int, int, Fraction, str] | None:
        candidates = [entity.geometry for entity in graph.entities]
        candidates += [relation.value or {} for relation in graph.relations]
        for data in candidates:
            grid = data.get("grid") if isinstance(data.get("grid"), dict) else data
            columns = grid.get("columns") or grid.get("cols")
            rows = grid.get("rows")
            cell_area = grid.get("cell_area") or grid.get("unit_cell_area")
            if isinstance(cell_area, dict):
                unit = str(cell_area.get("unit", "cm²"))
                cell_area = cell_area.get("number", cell_area.get("value"))
            else:
                unit = str(grid.get("area_unit", "cm²"))
            try:
                columns, rows = int(columns), int(rows)
                area = Fraction(str(cell_area))
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            if columns > 0 and rows > 0 and area > 0:
                return columns, rows, area, unit
        return None

    @staticmethod
    def _has_grid_metadata(data: dict[str, Any]) -> bool:
        grid = data.get("grid") if isinstance(data.get("grid"), dict) else data
        return bool((grid.get("columns") or grid.get("cols")) and grid.get("rows"))

    @staticmethod
    def _vertices(geometry: dict[str, Any]) -> list[list[float]] | None:
        raw = geometry.get("grid_vertices") or geometry.get("vertices") or geometry.get("points")
        if not isinstance(raw, list) or len(raw) < 3:
            return None
        points = []
        for point in raw:
            if isinstance(point, dict):
                x, y = point.get("x"), point.get("y")
            elif isinstance(point, (list, tuple)) and len(point) >= 2:
                x, y = point[0], point[1]
            else:
                return None
            try:
                points.append([float(x), float(y)])
            except (TypeError, ValueError):
                return None
        return points

    @staticmethod
    def _shoelace(points: list[list[float]]) -> Fraction:
        rational_points = [(Fraction(str(x)), Fraction(str(y))) for x, y in points]
        doubled = sum(
            x1 * y2 - y1 * x2
            for (x1, y1), (x2, y2) in zip(rational_points, rational_points[1:] + rational_points[:1])
        )
        return abs(doubled) / 2

    @staticmethod
    def _public(value: Fraction) -> int | float | str:
        if value.denominator == 1:
            return value.numerator
        return f"{value.numerator}/{value.denominator}"
