import json

from app.llm import LLMAdapter, LLMRequest, LLMResult
from app.math_verifier import SafeExpressionParser, SympyMathVerifier, UnsafeMathExpression
from app.models import ConfirmedProblem
from app.teacher_preparation import TeacherPreparationGenerator


class FakePreparationLLM(LLMAdapter):
    async def generate(self, request: LLMRequest) -> LLMResult:
        parsed = {
            "variables": ["small", "large"],
            "variable_meanings": {"small": "较小数量", "large": "较大数量"},
            "domain": {"small": "positive_integer", "large": "positive_integer"},
            "constraints": [
                {"left": "small + large", "right": "84", "source_text": "一共84"},
                {"left": "large - small", "right": "18", "source_text": "相差18"},
            ],
            "target_variables": ["small", "large"],
            "candidate_solutions": [{
                "method": "方程法", "age_appropriate": True,
                "steps": [
                    {"goal": "建立两个数量关系", "operation": "根据和与差列方程", "expression": "small+large=84; large-small=18"},
                    {"goal": "求出两个数量", "operation": "解方程并回代", "expression": None},
                ],
            }],
            "core_understandings": ["同时使用总量和差量关系"],
            "teaching_entries": ["先找两个量合起来是多少"],
        }
        return LLMResult(
            provider="fake", model="fake", content=json.dumps(parsed), parsed=parsed, latency_ms=1,
        )


def test_sympy_verifier_solves_and_checks_declarative_constraints():
    result = SympyMathVerifier().verify_system(
        ["small", "large"],
        [{"left": "small + large", "right": "84"}, {"left": "large - small", "right": "18"}],
        {"small": "positive_integer", "large": "positive_integer"},
    )
    assert result.status == "verified"
    assert result.public_solution() == {"small": 33, "large": 51}
    assert all(check["passed"] for check in result.checks)


def test_safe_parser_rejects_function_calls():
    try:
        SafeExpressionParser(["x"]).parse("__import__('os')")
    except UnsafeMathExpression:
        pass
    else:
        raise AssertionError("function call must be rejected")


def test_student_equation_is_verified_against_reference_constraint():
    result = SympyMathVerifier().verify_student_equation(
        "large-small=18",
        ["small", "large"],
        [{"left": "small + large", "right": "84"}, {"left": "large - small", "right": "18"}],
    )
    assert result["status"] == "verified"
    assert result["constraint_index"] == 1


async def test_unknown_problem_generates_verified_teacher_preparation():
    package = await TeacherPreparationGenerator(FakePreparationLLM()).generate(
        ConfirmedProblem(problem_id="new", confirmed_text="两个数和是84，差是18，求这两个数", match_score=0)
    )
    assert package.status == "ready"
    assert package.source == "generated_and_verified"
    assert package.verified_answer == {"small": 33, "large": 51}
    runtime = package.to_runtime_case(ConfirmedProblem(problem_id="new", confirmed_text="测试陌生题", match_score=0))
    assert runtime["preparation_source"] == "generated_and_verified"
    assert runtime["solution_paths"][0]["method"] == "方程法"
