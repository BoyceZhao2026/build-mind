import json
import re
from difflib import SequenceMatcher
from uuid import uuid4

from .llm import LLMAdapter, LLMRequest
from .models import GeneratedTutorReply, TeachingPolicy, TutorTurnResponse


class GuidedResponseGenerator:
    def __init__(self, adapter: LLMAdapter):
        self.adapter = adapter

    async def generate(
        self,
        response: TutorTurnResponse,
        policy: TeachingPolicy,
        student_text: str,
        final_answer: object | None,
        conversation_context: dict,
    ) -> tuple[GeneratedTutorReply | None, dict]:
        violations: list[str] = []
        for attempt in range(2):
            task = "guided_response_generation" if attempt == 0 else "guided_response_rewrite"
            try:
                candidate = await self._call_model(
                    task=task,
                    response=response,
                    policy=policy,
                    student_text=student_text,
                    previous_violations=violations,
                    conversation_context=conversation_context,
                )
            except Exception as exc:
                return None, {
                    "math_status": "unknown",
                    "state_consistent": True,
                    "leakage_safe": True,
                    "violations": [f"model_error:{type(exc).__name__}"],
                    "decision": "fallback",
                }

            violations = self._guard(candidate, response, final_answer, conversation_context)
            if not violations:
                return candidate, {
                    "math_status": "unknown",
                    "state_consistent": True,
                    "leakage_safe": True,
                    "violations": [],
                    "decision": "allow" if attempt == 0 else "rewrite",
                }

        return None, {
            "math_status": "unknown",
            "state_consistent": True,
            "leakage_safe": False,
            "violations": violations,
            "decision": "fallback",
        }

    async def _call_model(
        self,
        task: str,
        response: TutorTurnResponse,
        policy: TeachingPolicy,
        student_text: str,
        previous_violations: list[str],
        conversation_context: dict,
    ) -> GeneratedTutorReply:
        object_names = [obj.name for obj in response.state.problem.objects]
        prompt = {
            "problem": response.state.problem.confirmed_text,
            "student_turn": student_text,
            "intent": response.intent,
            "verdict": response.verdict,
            "teaching_policy": policy.model_dump(exclude={"fallback_text"}),
            "known_object_names": object_names,
            "conversation_context": conversation_context,
            "previous_violations": previous_violations,
        }
        result = await self.adapter.generate(LLMRequest(
            task=task,
            trace_id=str(uuid4()),
            temperature=0.2,
            response_schema={
                "type": "object",
                "properties": {
                    "speech": {"type": "string"},
                    "caption": {"type": "string"},
                    "blackboard_focus_objects": {"type": "array", "items": {"type": "string"}},
                    "blackboard_relation": {"type": ["string", "null"]},
                },
                "required": ["speech", "caption", "blackboard_focus_objects", "blackboard_relation"],
            },
            system_prompt=(
                "你是六年级数学引导老师。状态机已经决定教学动作，你只负责把策略表达得自然。"
                "一次只能提出一个问题，speech中最多出现一个问号；不直接给最终答案，不替学生完成当前关键步骤，不提前讲后续步骤。"
                "当teaching_policy.action=finish_session时，简短肯定学生已完成并结束本题，不再提出任何问题。"
                "必须承接学生刚才新增的理解；如果学生已回答current_question，不能再次询问同一事实。"
                "student_claims和understanding_evidence中已经出现的事实只能作为承接陈述，禁止再次用问题询问。"
                "避免重复recent_teacher_questions；需要继续追问时，应追问剩余缺口或原因，而不是换句话重复。"
                "只使用输入中的允许信息。speech适合口语朗读；caption不得增加speech没有的信息。"
                "黑板对象只能从known_object_names选择。只输出JSON。"
            ),
            user_prompt=json.dumps(prompt, ensure_ascii=False),
        ))
        return GeneratedTutorReply.model_validate(result.parsed)

    @staticmethod
    def _answer_numbers(answer: object | None) -> list[str]:
        return re.findall(r"\d+(?:\.\d+)?", str(answer)) if answer is not None else []

    def _guard(
        self,
        candidate: GeneratedTutorReply,
        response: TutorTurnResponse,
        final_answer: object | None,
        conversation_context: dict | None = None,
    ) -> list[str]:
        violations: list[str] = []
        combined = f"{candidate.speech}\n{candidate.caption}\n{candidate.blackboard_relation or ''}"
        for value in self._answer_numbers(final_answer):
            if re.search(rf"(?<!\d){re.escape(value)}(?!\d)", combined):
                violations.append("final_answer_number")
                break
        if any(phrase in combined for phrase in ["答案是", "最终答案", "直接算出", "所以答案"]):
            violations.append("explicit_answer_phrase")
        known_names = {obj.name for obj in response.state.problem.objects}
        if any(name not in known_names for name in candidate.blackboard_focus_objects):
            violations.append("unknown_blackboard_object")
        if candidate.speech.count("？") + candidate.speech.count("?") > 1:
            violations.append("too_many_questions")
        prior_questions = (conversation_context or {}).get("recent_teacher_questions", [])
        candidate_question = self._extract_question(candidate.speech)
        if candidate_question and any(
            self._question_similarity(candidate_question, prior) >= 0.82
            for prior in prior_questions
            if isinstance(prior, str)
        ):
            violations.append("repeated_question")
        return sorted(set(violations))

    @staticmethod
    def _extract_question(text: str) -> str | None:
        questions = re.findall(r"[^。！？!?]*[？?]", text)
        return questions[-1].strip() if questions else None

    @staticmethod
    def _question_similarity(left: str, right: str) -> float:
        normalize = lambda value: re.sub(r"[\s，。！？、,.!?‘’“”'\"]", "", value)
        normalized_left = normalize(left)
        normalized_right = normalize(right)
        if not normalized_left or not normalized_right:
            return 0.0
        return SequenceMatcher(None, normalized_left, normalized_right).ratio()
