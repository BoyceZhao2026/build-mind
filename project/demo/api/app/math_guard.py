import re

from sympy import Eq, simplify, sympify


def expressions_equivalent(left: str, right: str) -> bool | None:
    """比较两个简单算式；无法安全解析时返回 None，不猜测。"""
    try:
        return bool(simplify(sympify(left) - sympify(right)) == 0)
    except Exception:
        return None


def contains_final_answer(text: str, answer: object) -> bool:
    values = re.findall(r"\d+(?:\.\d+)?", str(answer))
    return any(re.search(rf"(?<!\d){re.escape(value)}(?!\d)", text) for value in values)
