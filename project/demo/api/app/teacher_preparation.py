from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from .llm import LLMAdapter, LLMRequest
from .math_verifier import SympyMathVerifier
from .models import ConfirmedProblem
from .diagram_solver import DiagramGraphSolver


class DeclarativeConstraint(BaseModel):
    left: str
    right: str
    source_text: str


class PreparationStep(BaseModel):
    goal: str
    operation: str
    expression: str | None = None


class CandidatePreparationSolution(BaseModel):
    method: str
    age_appropriate: bool = True
    steps: list[PreparationStep] = Field(min_length=1, max_length=8)


class TeacherPreparationPackage(BaseModel):
    preparation_id: str = Field(default_factory=lambda: str(uuid4()))
    status: Literal["ready", "partially_ready", "failed"]
    source: Literal["generated_and_verified", "generated_unverified", "fallback"]
    variables: list[str] = Field(default_factory=list)
    variable_meanings: dict[str, str] = Field(default_factory=dict)
    domain: dict[str, str] = Field(default_factory=dict)
    constraints: list[DeclarativeConstraint] = Field(default_factory=list)
    target_variables: list[str] = Field(default_factory=list)
    candidate_solutions: list[CandidatePreparationSolution] = Field(default_factory=list)
    core_understandings: list[str] = Field(default_factory=list)
    teaching_entries: list[str] = Field(default_factory=list)
    verified_answer: dict[str, Any] | None = None
    verification: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    def to_runtime_case(self, problem: ConfirmedProblem) -> dict[str, Any]:
        paths = []
        for path_index, candidate in enumerate(self.candidate_solutions, start=1):
            steps = []
            for step_index, step in enumerate(candidate.steps, start=1):
                step_id = f"generated_{path_index}_{step_index}"
                steps.append({
                    "step_id": step_id,
                    "depends_on": [] if step_index == 1 else [f"generated_{path_index}_{step_index - 1}"],
                    "goal": step.goal,
                    "operation": step.operation,
                    "expression_after": step.expression,
                })
            paths.append({
                "path_id": f"generated_path_{path_index}",
                "method": candidate.method,
                "age_appropriate": candidate.age_appropriate,
                "steps": steps,
            })
        return {
            "case_id": f"dynamic:{self.preparation_id}",
            "preparation_source": self.source,
            "preparation_status": self.status,
            "constraints": [item.model_dump() for item in self.constraints],
            "variables": self.variables,
            "core_understandings": self.core_understandings,
            "teaching_entries": self.teaching_entries,
            "answer": {
                "final_value": self.verified_answer,
                "unit": "由题目对象定义",
                "validation_expression": "; ".join(f"{item.left}={item.right}" for item in self.constraints),
                "internal_only": True,
            } if self.verified_answer else None,
            "solution_paths": paths,
            "problem": {"text": problem.confirmed_text, "question": problem.question},
        }


class TeacherPreparationGenerator:
    def __init__(self, llm: LLMAdapter | None, verifier: SympyMathVerifier | None = None, diagram_solver: DiagramGraphSolver | None = None):
        self.llm = llm
        self.verifier = verifier or SympyMathVerifier()
        self.diagram_solver = diagram_solver or DiagramGraphSolver()

    async def generate(self, problem: ConfirmedProblem) -> TeacherPreparationPackage:
        if problem.diagram_graph:
            diagram_result = self.diagram_solver.solve(problem.diagram_graph)
            if diagram_result.status == "verified":
                return TeacherPreparationPackage(
                    status="ready",
                    source="generated_and_verified",
                    variables=["target_area"],
                    variable_meanings={"target_area": "题目所求图形的面积"},
                    domain={"target_area": "positive"},
                    constraints=[DeclarativeConstraint.model_validate(item) for item in diagram_result.constraints],
                    target_variables=["target_area"],
                    candidate_solutions=[CandidatePreparationSolution(
                        method="网格坐标面积法（可用分割或补形向学生解释）",
                        age_appropriate=True,
                        steps=[PreparationStep.model_validate(step) for step in diagram_result.solution_steps],
                    )],
                    core_understandings=diagram_result.core_understandings,
                    teaching_entries=["先请学生说出各顶点位于哪些网格交点", "再让学生选择分割法或补形法"],
                    verified_answer=diagram_result.answer,
                    verification={
                        "status": "verified",
                        "engine": "geometry_kernel+sympy",
                        "facts": diagram_result.facts,
                        "trace": diagram_result.verification_trace,
                    },
                )
            return TeacherPreparationPackage(
                status="partially_ready",
                source="generated_unverified",
                verification={"status": diagram_result.status, "missing_facts": diagram_result.missing_facts},
                error="；".join(diagram_result.missing_facts) or "图形暂不在几何内核支持范围内",
            )
        if self.llm is None:
            return TeacherPreparationPackage(
                status="failed", source="fallback", error="未配置教师备课模型",
            )
        try:
            result = await self.llm.generate(LLMRequest(
                task="teacher_preparation",
                trace_id=str(uuid4()),
                temperature=0,
                response_schema=self._schema(),
                system_prompt=(
                    "你是六年级数学教师的备课模块。先独立理解并完整解题，但输出必须是结构化备课数据。"
                    "变量只使用英文字母、数字和下划线；方程左右侧只允许变量、整数、小数、括号和+-*/^。"
                    "不要在方程中写单位或中文。生成1到2种适龄方法，不把参考方法当成学生必须遵循的顺序。"
                    "不得省略题目关键条件；未知量默认使用positive或positive_integer定义域。"
                ),
                user_prompt=f"题目：{problem.confirmed_text}\n问题目标：{problem.question or '根据题目确定'}",
            ))
            payload = result.parsed or {}
            constraints = [DeclarativeConstraint.model_validate(item) for item in payload.get("constraints", [])]
            candidates = [CandidatePreparationSolution.model_validate(item) for item in payload.get("candidate_solutions", [])]
            verification = self.verifier.verify_system(
                payload.get("variables", []),
                [item.model_dump() for item in constraints],
                payload.get("domain", {}),
            )
            verified = verification.status == "verified"
            return TeacherPreparationPackage(
                status="ready" if verified and candidates else "partially_ready",
                source="generated_and_verified" if verified else "generated_unverified",
                variables=payload.get("variables", []),
                variable_meanings=payload.get("variable_meanings", {}),
                domain=payload.get("domain", {}),
                constraints=constraints,
                target_variables=payload.get("target_variables", []),
                candidate_solutions=candidates,
                core_understandings=payload.get("core_understandings", []),
                teaching_entries=payload.get("teaching_entries", []),
                verified_answer=verification.public_solution() if verified else None,
                verification={
                    "status": verification.status,
                    "checks": verification.checks,
                    "error": verification.error,
                },
            )
        except Exception as exc:
            return TeacherPreparationPackage(
                status="failed", source="generated_unverified", error=f"{type(exc).__name__}: {exc}",
            )

    @staticmethod
    def _schema() -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "variables": {"type": "array", "items": {"type": "string"}},
                "variable_meanings": {"type": "object", "additionalProperties": {"type": "string"}},
                "domain": {"type": "object", "additionalProperties": {"enum": ["positive", "positive_integer", "nonnegative", "real"]}},
                "constraints": {"type": "array", "items": {"type": "object", "properties": {
                    "left": {"type": "string"}, "right": {"type": "string"}, "source_text": {"type": "string"},
                }, "required": ["left", "right", "source_text"]}},
                "target_variables": {"type": "array", "items": {"type": "string"}},
                "candidate_solutions": {"type": "array", "items": {"type": "object", "properties": {
                    "method": {"type": "string"}, "age_appropriate": {"type": "boolean"},
                    "steps": {"type": "array", "items": {"type": "object", "properties": {
                        "goal": {"type": "string"}, "operation": {"type": "string"},
                        "expression": {"type": ["string", "null"]},
                    }, "required": ["goal", "operation", "expression"]}},
                }, "required": ["method", "age_appropriate", "steps"]}},
                "core_understandings": {"type": "array", "items": {"type": "string"}},
                "teaching_entries": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "variables", "variable_meanings", "domain", "constraints", "target_variables",
                "candidate_solutions", "core_understandings", "teaching_entries",
            ],
        }
