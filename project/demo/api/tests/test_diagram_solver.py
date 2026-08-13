import pytest

from app.diagram_solver import DiagramGraphSolver
from app.models import ConfirmedProblem
from app.teacher_preparation import TeacherPreparationGenerator


def confirmed_grid_graph():
    return {
        "diagram_id": "grid_area_1",
        "diagram_type": "geometry",
        "status": "confirmed",
        "entities": [
            {
                "entity_id": "grid",
                "type": "region",
                "geometry": {"grid": {"columns": 8, "rows": 6, "cell_area": {"number": 1, "unit": "cm²"}}},
                "status": "confirmed",
            },
            {
                "entity_id": "target",
                "type": "polygon",
                "geometry": {"coordinate_space": "grid", "grid_vertices": [[1, 4], [3, 1], [7, 2], [5, 5]]},
                "status": "confirmed",
            },
        ],
    }


def test_confirmed_grid_polygon_becomes_verified_geometry_model():
    result = DiagramGraphSolver().solve(confirmed_grid_graph())

    assert result.status == "verified"
    assert result.answer == {"target_area": 14}
    assert result.constraints == [{"left": "target_area", "right": "14", "source_text": "网格多边形面积约束"}]
    assert result.verification_trace[0]["substitution_passed"] is True


def test_grid_polygon_without_grid_scale_reports_missing_facts():
    graph = confirmed_grid_graph()
    graph["entities"][0]["geometry"] = {}

    result = DiagramGraphSolver().solve(graph)

    assert result.status == "insufficient_facts"
    assert "缺少网格行列数或单格面积" in result.missing_facts


def test_normalized_image_vertices_are_not_treated_as_grid_coordinates():
    graph = confirmed_grid_graph()
    graph["entities"][1]["geometry"] = {
        "coordinate_space": "normalized",
        "vertices": [[0.3, 0.4], [0.5, 0.2], [0.7, 0.4], [0.5, 0.7]],
    }

    result = DiagramGraphSolver().solve(graph)

    assert result.status == "insufficient_facts"
    assert "格点坐标" in result.missing_facts[0]


@pytest.mark.asyncio
async def test_teacher_preparation_uses_verified_diagram_before_llm():
    problem = ConfirmedProblem(
        problem_id="diagram-problem",
        confirmed_text="求网格中四边形的面积，每格1平方厘米",
        match_score=0,
        diagram_graph=confirmed_grid_graph(),
    )

    package = await TeacherPreparationGenerator(None).generate(problem)

    assert package.status == "ready"
    assert package.verified_answer == {"target_area": 14}
    assert package.verification["engine"] == "geometry_kernel+sympy"
