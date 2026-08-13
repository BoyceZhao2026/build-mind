from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from sympy import Add, Eq, Integer, Mul, Pow, Rational, Symbol, simplify, solve
from sympy.core.expr import Expr


class UnsafeMathExpression(ValueError):
    pass


class SafeExpressionParser:
    """Parse a deliberately small arithmetic language without eval/sympify."""

    def __init__(self, variable_names: list[str]):
        self.symbols = {name: Symbol(name, real=True) for name in variable_names}

    def parse(self, source: str) -> Expr:
        normalized = source.strip().replace("^", "**")
        if len(normalized) > 300:
            raise UnsafeMathExpression("表达式过长")
        try:
            tree = ast.parse(normalized, mode="eval")
        except SyntaxError as exc:
            raise UnsafeMathExpression("表达式语法错误") from exc
        return self._convert(tree.body)

    def _convert(self, node: ast.AST) -> Expr:
        if isinstance(node, ast.Name):
            if node.id not in self.symbols:
                raise UnsafeMathExpression(f"未声明变量：{node.id}")
            return self.symbols[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return Rational(str(node.value))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = self._convert(node.operand)
            return value if isinstance(node.op, ast.UAdd) else Mul(Integer(-1), value)
        if isinstance(node, ast.BinOp):
            left, right = self._convert(node.left), self._convert(node.right)
            if isinstance(node.op, ast.Add):
                return Add(left, right)
            if isinstance(node.op, ast.Sub):
                return Add(left, Mul(Integer(-1), right))
            if isinstance(node.op, ast.Mult):
                return Mul(left, right)
            if isinstance(node.op, ast.Div):
                return Mul(left, Pow(right, Integer(-1)))
            if isinstance(node.op, ast.Pow):
                if not right.is_number:
                    raise UnsafeMathExpression("指数必须是数值")
                return Pow(left, right)
        raise UnsafeMathExpression(f"不支持的表达式节点：{type(node).__name__}")


@dataclass
class VerificationResult:
    status: str
    equations: list[Eq]
    solution: dict[str, Expr]
    checks: list[dict[str, Any]]
    error: str | None = None

    def public_solution(self) -> dict[str, int | float | str]:
        result: dict[str, int | float | str] = {}
        for name, value in self.solution.items():
            if value.is_Integer:
                result[name] = int(value)
            elif value.is_Rational:
                result[name] = f"{value.p}/{value.q}"
            elif value.is_real:
                result[name] = float(value)
            else:
                result[name] = str(value)
        return result


class SympyMathVerifier:
    def verify_system(
        self,
        variables: list[str],
        constraints: list[dict[str, str]],
        domain: dict[str, str] | None = None,
    ) -> VerificationResult:
        if not variables or len(variables) > 12:
            return VerificationResult("invalid", [], {}, [], "变量数量不在允许范围内")
        if len(set(variables)) != len(variables) or any(not name.isidentifier() for name in variables):
            return VerificationResult("invalid", [], {}, [], "变量名称不合法或重复")
        parser = SafeExpressionParser(variables)
        try:
            equations = [Eq(parser.parse(item["left"]), parser.parse(item["right"])) for item in constraints]
        except (KeyError, UnsafeMathExpression, TypeError) as exc:
            return VerificationResult("invalid", [], {}, [], str(exc))
        if not equations:
            return VerificationResult("invalid", [], {}, [], "没有可验证方程")
        symbols = [parser.symbols[name] for name in variables]
        try:
            solutions = solve(equations, symbols, dict=True)
        except Exception as exc:
            return VerificationResult("unsupported", equations, {}, [], type(exc).__name__)
        if len(solutions) != 1 or any(symbol not in solutions[0] for symbol in symbols):
            return VerificationResult("underdetermined", equations, {}, [], "方程组没有唯一完整解")
        solution_by_symbol = solutions[0]
        checks = []
        for index, equation in enumerate(equations):
            passed = simplify(equation.lhs.subs(solution_by_symbol) - equation.rhs.subs(solution_by_symbol)) == 0
            checks.append({"constraint_index": index, "passed": bool(passed)})
        solution = {name: solution_by_symbol[parser.symbols[name]] for name in variables}
        domain_error = self._check_domain(solution, domain or {})
        if domain_error:
            return VerificationResult("invalid", equations, solution, checks, domain_error)
        status = "verified" if all(check["passed"] for check in checks) else "invalid"
        return VerificationResult(status, equations, solution, checks)

    @staticmethod
    def _check_domain(solution: dict[str, Expr], domain: dict[str, str]) -> str | None:
        for name, rule in domain.items():
            value = solution.get(name)
            if value is None:
                continue
            if rule in {"positive", "positive_integer", "nonnegative"} and value.is_real is not True:
                return f"{name} 不是实数"
            if rule in {"positive", "positive_integer"} and value.is_positive is not True:
                return f"{name} 不满足正数约束"
            if rule == "positive_integer" and value.is_integer is not True:
                return f"{name} 不满足正整数约束"
            if rule == "nonnegative" and value.is_nonnegative is not True:
                return f"{name} 不满足非负约束"
        return None

    def verify_student_equation(
        self,
        expression: str,
        variables: list[str],
        reference_constraints: list[dict[str, str]],
    ) -> dict[str, Any]:
        if "=" not in expression or expression.count("=") != 1:
            return {"status": "unsupported", "reason": "当前只验证单个等式"}
        parser = SafeExpressionParser(variables)
        left_text, right_text = expression.split("=", 1)
        try:
            claim = parser.parse(left_text) - parser.parse(right_text)
            references = [parser.parse(item["left"]) - parser.parse(item["right"]) for item in reference_constraints]
        except (UnsafeMathExpression, KeyError) as exc:
            return {"status": "unsupported", "reason": str(exc)}
        for index, reference in enumerate(references):
            if simplify(claim - reference) == 0 or simplify(claim + reference) == 0:
                return {"status": "verified", "basis": "equivalent_constraint", "constraint_index": index}
            if reference != 0 and simplify(claim / reference).is_number:
                return {"status": "verified", "basis": "proportional_constraint", "constraint_index": index}
        if not claim.free_symbols:
            return {"status": "verified" if simplify(claim) == 0 else "rejected", "basis": "exact_arithmetic"}
        return {"status": "unverified", "reason": "等式未与备课约束形成可证明的等价关系"}
