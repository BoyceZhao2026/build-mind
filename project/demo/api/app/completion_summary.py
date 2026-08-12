import json
import re
from uuid import uuid4

from .llm import LLMAdapter, LLMRequest
from .models import CompletionSummary
from .tutor import SessionRecord


class CompletionSummaryGenerator:
    def __init__(self, adapter: LLMAdapter | None):
        self.adapter = adapter

    async def generate(self, record: SessionRecord, trigger: str) -> CompletionSummary:
        safe_trigger = "student" if trigger == "student" else "system"
        if self.adapter is None:
            return self._fallback(record, safe_trigger)
        payload = {
            "problem": record.state.problem.confirmed_text,
            "student_method_summary": record.state.student_method_summary,
            "reasoning_graph": [node.model_dump() for node in record.state.reasoning_nodes],
            "conversation_history": [
                {"student": turn.student_text, "teacher": turn.assistant_text}
                for turn in record.turns
            ],
            "trigger": safe_trigger,
        }
        try:
            result = await self.adapter.generate(LLMRequest(
                task="completion_summary_generation",
                trace_id=str(uuid4()),
                temperature=0.1,
                response_schema={
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "method": {"type": "string"},
                        "key_relationship": {"type": "string"},
                        "steps": {"type": "array", "items": {"type": "string"}},
                        "common_pitfall": {"type": ["string", "null"]},
                        "closing_message": {"type": "string"},
                        "trigger": {"enum": ["student", "system"]},
                    },
                    "required": [
                        "title", "method", "key_relationship", "steps",
                        "common_pitfall", "closing_message", "trigger",
                    ],
                },
                system_prompt=(
                    "你负责在六年级数学辅导结束时，帮助学生第二次梳理解题思路。"
                    "以学生已经采用的方法为主线，可以把它整理成完整的通用解题步骤，但不得代算具体结果、给出最终答案或引入另一种内部参考解法。"
                    "忽略rejected节点；unverified节点只能表述为仍需留意，不能写成确定结论。"
                    "steps保持2到5条、简短、有顺序；重点说明关键数量关系和方法，不重复完整题干。"
                    "会话已经结束，closing_message只能收口和提醒以后如何自检，禁止再提问、布置下一步或邀请继续计算。只输出JSON。"
                ),
                user_prompt=json.dumps(payload, ensure_ascii=False),
            ))
            summary = CompletionSummary.model_validate(result.parsed)
            summary.trigger = safe_trigger
            return self._sanitize(summary, record)
        except Exception:
            return self._fallback(record, safe_trigger)

    @staticmethod
    def _fallback(record: SessionRecord, trigger: str) -> CompletionSummary:
        usable = [
            node for node in record.state.reasoning_nodes
            if node.verification_status in {"verified", "partially_verified"}
        ]
        steps = [node.claim for node in usable[-5:]]
        method = record.state.student_method_summary or "根据题目条件逐步建立数量关系"
        relationship = next(
            (node.normalized_math for node in reversed(usable) if node.normalized_math),
            "把已知条件与所求问题联系起来",
        )
        if not steps:
            steps = ["识别题目中的已知量和未知量", "根据条件建立它们之间的数量关系"]
        return CompletionSummary(
            method=method,
            key_relationship=relationship,
            steps=steps,
            common_pitfall="列式或计算后，记得回到题目条件中检查是否一致。",
            closing_message="这道题先总结到这里。以后再遇到类似问题，可以先找关键数量关系，再选择合适的方法。",
            trigger=trigger,
        )

    @staticmethod
    def _sanitize(summary: CompletionSummary, record: SessionRecord) -> CompletionSummary:
        answer = (record.gold_case or {}).get("answer", {}).get("final_value")
        final_numbers = re.findall(r"\d+(?:\.\d+)?", str(answer)) if answer is not None else []

        def leaks_final(text: str) -> bool:
            return any(re.search(rf"(?<!\d){re.escape(value)}(?!\d)", text) for value in final_numbers)

        summary.steps = [step for step in summary.steps[:5] if not leaks_final(step)]
        if not summary.steps:
            summary.steps = ["根据题目条件找出已知量、未知量和关键数量关系", "沿已经确认的方法列式，并用原题条件检查结果"]
        if leaks_final(summary.key_relationship):
            summary.key_relationship = "把题目中的总量关系和差量或倍数关系联系起来"
        if leaks_final(summary.method):
            summary.method = record.state.student_method_summary or "根据关键数量关系逐步推理"
        closing_has_new_task = any(word in summary.closing_message for word in ["下一步", "试试", "请你", "可以算出", "？", "?"])
        if closing_has_new_task or leaks_final(summary.closing_message):
            summary.closing_message = "这道题的思路已经整理好了。以后遇到类似问题，可以先找关键数量关系，再用题目条件检查自己的推理。"
        return summary
