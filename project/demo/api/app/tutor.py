import re
from dataclasses import dataclass, field
from uuid import uuid4

from .models import (
    BlackboardPatch,
    ConfirmedProblem,
    SessionState,
    StudentReasoningNode,
    TeachingPolicy,
    TutorContext,
    TutorTurnResponse,
)


@dataclass
class SessionRecord:
    state: SessionState
    gold_case: dict | None
    turns: list[TutorTurnResponse] = field(default_factory=list)
    context: TutorContext = field(default_factory=TutorContext)


class TutorEngine:
    def __init__(self):
        self.sessions: dict[str, SessionRecord] = {}

    def create_session(self, problem: ConfirmedProblem, gold_case: dict | None) -> SessionState:
        session_id = str(uuid4())
        task = "先说说你准备怎样分析题目中的数量关系"
        state = SessionState(
            session_id=session_id,
            phase="orient",
            current_task=task,
            problem=problem,
        )
        paths = self._paths_from_case(gold_case)
        state.frontier_step_ids = self._frontier_ids(gold_case, state.completed_step_ids)
        opening_question = "你目前有什么想法？"
        context = TutorContext(
            current_question_id=str(uuid4()),
            current_question=opening_question,
            unresolved_questions=[opening_question],
            recent_teacher_questions=[opening_question],
        )
        self.sessions[session_id] = SessionRecord(state=state, gold_case=gold_case, context=context)
        return state

    def complete_session(self, session_id: str) -> SessionState:
        state = self.sessions[session_id].state
        state.phase = "complete"
        state.current_task = "本题辅导已完成"
        return state

    def context_snapshot(self, session_id: str, include_latest_turn: bool = True) -> dict:
        record = self.sessions[session_id]
        turns = record.turns if include_latest_turn else record.turns[:-1]
        all_messages: list[dict[str, str]] = []
        for turn in turns:
            all_messages.extend([
                {"role": "student", "text": turn.student_text},
                {"role": "assistant", "text": turn.assistant_text},
            ])
        return {
            "current_question_id": record.context.current_question_id,
            "current_question": record.context.current_question,
            "conversation_history": all_messages,
            "recent_turns": all_messages,
            "understanding_evidence": record.context.understanding_evidence,
            "unresolved_questions": record.context.unresolved_questions,
            "misconceptions": record.context.misconceptions,
            "student_claims": record.context.student_claims,
            "recent_teacher_questions": record.context.recent_teacher_questions,
            "pending_incomplete_utterance": record.context.pending_incomplete_utterance,
        }

    def _steps(self, record: SessionRecord) -> list[dict]:
        paths = self._paths_from_case(record.gold_case)
        active = next((path for path in paths if path.get("path_id") == record.state.active_path_id), None)
        return (active or (paths[0] if paths else {})).get("steps", [])

    @staticmethod
    def _paths_from_case(gold_case: dict | None) -> list[dict]:
        return (gold_case or {}).get("solution_paths", [])

    def solution_catalog(self, record: SessionRecord) -> list[dict]:
        """Return a compact, answer-free catalog for thought alignment."""
        catalog = []
        for path in self._paths_from_case(record.gold_case):
            catalog.append({
                "path_id": path.get("path_id"),
                "method": path.get("method"),
                "steps": [{
                    "step_id": step.get("step_id"),
                    "depends_on": step.get("depends_on", []),
                    "goal": step.get("goal"),
                    "action": step.get("action"),
                    "operation": step.get("operation"),
                    "required_understanding": step.get("required_understanding"),
                } for step in path.get("steps", [])],
            })
        return catalog

    def _step_map(self, record: SessionRecord) -> dict[str, tuple[dict, dict]]:
        return {
            step["step_id"]: (path, step)
            for path in self._paths_from_case(record.gold_case)
            for step in path.get("steps", [])
            if step.get("step_id")
        }

    def _frontier_ids(self, gold_case: dict | None, completed: list[str]) -> list[str]:
        done = set(completed)
        frontier = []
        for path in self._paths_from_case(gold_case):
            for step in path.get("steps", []):
                step_id = step.get("step_id")
                if step_id and step_id not in done and set(step.get("depends_on", [])).issubset(done):
                    frontier.append(step_id)
        return frontier

    def _choose_next_step(self, record: SessionRecord) -> dict | None:
        step_map = self._step_map(record)
        active_frontier = [
            step_map[step_id][1] for step_id in record.state.frontier_step_ids
            if step_id in step_map and step_map[step_id][0].get("path_id") == record.state.active_path_id
        ]
        if active_frontier:
            return active_frontier[0]
        return step_map[record.state.frontier_step_ids[0]][1] if record.state.frontier_step_ids else None

    def _first_task(self, gold_case: dict | None, problem: ConfirmedProblem) -> str:
        paths = (gold_case or {}).get("solution_paths", [])
        if paths and paths[0].get("steps"):
            return paths[0]["steps"][0].get("goal", "先说说你看到了哪些数量关系")
        return "先找出题目中的已知量、未知量和它们之间的关系"

    @staticmethod
    def _intent(text: str) -> str:
        if any(word in text for word in ["你错", "不对", "算错", "讲错"]):
            return "challenge_ai"
        if any(word in text for word in ["不会", "不懂", "不知道", "没思路"]):
            return "request_help"
        if any(word in text for word in ["答案", "直接告诉", "等于多少"]):
            return "request_answer"
        return "attempt"

    @staticmethod
    def _leaks_answer(text: str, gold_case: dict | None) -> bool:
        answer = (gold_case or {}).get("answer", {}).get("final_value")
        if answer is None:
            return False
        values = re.findall(r"\d+(?:\.\d+)?", str(answer))
        return any(re.search(rf"(?<!\d){re.escape(value)}(?!\d)", text) for value in values)

    def respond(
        self,
        session_id: str,
        student_text: str,
        model_analysis: dict | None = None,
    ) -> TutorTurnResponse:
        record = self.sessions[session_id]
        state = record.state
        steps = self._steps(record)
        allowed_intents = {"challenge_ai", "request_help", "request_answer", "attempt"}
        inferred_intent = (model_analysis or {}).get("intent")
        intent = inferred_intent if inferred_intent in allowed_intents else self._intent(student_text)
        lower = student_text.lower()

        if intent == "challenge_ai":
            verdict = "unknown"
            assistant = "谢谢你指出来。我们先暂停推进。你觉得我刚才哪一句或哪个关系不对？请指出来，我们一起重新核对题目条件。"
        elif intent == "request_answer":
            verdict = "unknown"
            assistant = f"我先不直接给结果。我们只看当前这一步：{state.current_task}。你能先说出应该用哪两个已知条件吗？"
        elif intent == "request_help":
            verdict = "unknown"
            state.hint_level = min(4, state.hint_level + 1)
            assistant = self._hint(record, state.current_step_index, state.hint_level)
        else:
            step_map = self._step_map(record)
            selected_id = (model_analysis or {}).get("selected_step_id")
            current = step_map.get(selected_id, (None, self._choose_next_step(record)))[1]
            allowed_verdicts = {"correct", "partially_correct", "incorrect", "unknown"}
            inferred_verdict = (model_analysis or {}).get("verdict")
            verdict = inferred_verdict if inferred_verdict in allowed_verdicts else self._judge(student_text, current, record.gold_case)
            if verdict == "correct":
                covered = (model_analysis or {}).get("covered_step_ids", [])
                valid_covered = [step_id for step_id in covered if step_id in step_map]
                if not valid_covered and selected_id in step_map:
                    valid_covered = [selected_id]
                for step_id in valid_covered:
                    if step_id not in state.completed_step_ids:
                        state.completed_step_ids.append(step_id)
                    path, step = step_map[step_id]
                    label = step.get("goal", step_id)
                    if label not in state.confirmed_steps:
                        state.confirmed_steps.append(label)
                    state.active_path_id = path.get("path_id")
                state.frontier_step_ids = self._frontier_ids(record.gold_case, state.completed_step_ids)
                active_steps = self._steps(record)
                state.current_step_index = next((
                    index for index, step in enumerate(active_steps)
                    if step.get("step_id") not in state.completed_step_ids
                ), len(active_steps))
                state.hint_level = 1
                next_subgoal = (model_analysis or {}).get("next_subgoal")
                solution_status = (model_analysis or {}).get("solution_status", "in_progress")
                if self._looks_like_completion(next_subgoal):
                    solution_status = "solved"
                if isinstance(model_analysis, dict):
                    model_analysis["solution_status"] = solution_status
                next_step = self._choose_next_step(record) if valid_covered else None
                if solution_status == "understanding_verified" or (
                    solution_status == "solved" and state.phase == "reflect"
                ):
                    state.phase = "complete"
                    state.current_task = "本题辅导已完成"
                    assistant = "很好，这道题你已经完成，也能说明关键关系为什么成立。本题辅导到这里结束，可以休息一下或换一道题。"
                elif solution_status == "solved":
                    state.phase = "reflect"
                    state.current_task = "用自己的话说明解题中的关键数量关系"
                    assistant = "你已经完成了解答。结束前请再用自己的话说一说：这道题最关键的数量关系是什么？"
                elif isinstance(next_subgoal, str) and next_subgoal.strip():
                    state.current_task = next_subgoal.strip()
                    state.phase = "attempt"
                    assistant = f"这个思路可以继续。下一步我们只看：{state.current_task}。你准备怎么做？"
                elif next_step:
                    state.current_task = next_step.get("goal", "继续下一步")
                    state.phase = "attempt"
                    assistant = f"这个方向成立。你是根据什么条件想到的？接下来我们只看：{state.current_task}。你准备怎样表示？"
                elif step_map:
                    state.phase = "reflect"
                    state.current_task = "用自己的话解释为什么这条数量关系成立"
                    assistant = "主要步骤已经走通了，但先不急着报最终结果。请你用自己的话解释：为什么刚才的等量关系成立？"
                else:
                    state.current_task = "说明你准备使用的数量关系"
                    assistant = "这个思路有可能成立。为了避免跳步，请先说清楚：等号两边分别表示什么？"
            elif verdict == "partially_correct":
                assistant = f"你已经抓到一部分了。先别继续计算，请补充说明：{state.current_task}里，每个量分别代表什么？"
            else:
                assistant = self._hint(record, state.current_step_index, min(4, state.hint_level + 1))
                state.hint_level = min(4, state.hint_level + 1)

        if self._leaks_answer(assistant, record.gold_case):
            assistant = f"我们先不看最终数值。请只完成当前小任务：{state.current_task}。你认为应该建立什么关系？"

        self._apply_context_analysis(record, student_text, verdict, model_analysis)

        analysis = model_analysis or {}
        self._update_reasoning_graph(state, analysis)
        valid_candidates = [item.get("step_id") for item in analysis.get("step_candidates", []) if isinstance(item, dict)]
        state.candidate_step_ids = [step_id for step_id in valid_candidates if step_id in self._step_map(record)][:3]
        allowed_alignments = {"aligned", "jumped_ahead", "alternative_path", "new_valid_path", "ambiguous", "unknown"}
        alignment = analysis.get("alignment")
        state.thought_alignment = alignment if alignment in allowed_alignments else "unknown"
        confidence = analysis.get("confidence", 0)
        state.thought_confidence = max(0.0, min(1.0, float(confidence))) if isinstance(confidence, (int, float)) else 0.0
        method_summary = analysis.get("student_method_summary")
        if isinstance(method_summary, str) and method_summary.strip():
            state.student_method_summary = method_summary.strip()

        state.turn_count += 1
        focus = [obj.name for obj in state.problem.objects[:4]]
        relation = None
        next_step = self._choose_next_step(record)
        if next_step:
            relation = next_step.get("goal")
        response = TutorTurnResponse(
            turn_id=str(uuid4()),
            student_text=student_text,
            intent=intent,
            verdict=verdict,
            assistant_text=assistant,
            caption=assistant,
            state=state,
            blackboard=BlackboardPatch(
                current_task=state.current_task,
                focus_objects=focus,
                relation=relation,
                confirmed_steps=state.confirmed_steps,
            ),
            guard={"math_status": "unknown", "leakage_safe": True, "decision": "allow"},
            business_trace=self._business_trace(state, intent, verdict, analysis),
        )
        record.turns.append(response)
        return response

    @staticmethod
    def _looks_like_completion(next_subgoal: object) -> bool:
        if not isinstance(next_subgoal, str):
            return False
        normalized = re.sub(r"[\s（）()：:]", "", next_subgoal)
        return normalized in {"无", "已完成", "当前小任务已完成", "本题已完成"} or normalized.startswith("无当前")

    @staticmethod
    def _update_reasoning_graph(state: SessionState, analysis: dict) -> None:
        existing = {node.node_id for node in state.reasoning_nodes}
        for item in analysis.get("reasoning_nodes", []):
            if not isinstance(item, dict):
                continue
            node_id = item.get("node_id")
            if not isinstance(node_id, str) or not node_id or node_id in existing:
                continue
            try:
                node = StudentReasoningNode.model_validate(item)
            except Exception:
                continue
            state.reasoning_nodes.append(node)
            existing.add(node.node_id)

    @staticmethod
    def _business_trace(state: SessionState, intent: str, verdict: str, analysis: dict) -> dict:
        return {
            "intent": intent,
            "verdict": verdict,
            "method_summary": state.student_method_summary,
            "alignment": state.thought_alignment,
            "confidence": state.thought_confidence,
            "new_reasoning_nodes": analysis.get("reasoning_nodes", []),
            "reasoning_graph": [node.model_dump() for node in state.reasoning_nodes],
            "reference_match": {
                "active_path_id": state.active_path_id,
                "candidate_step_ids": state.candidate_step_ids,
                "note": "仅作可选参考；未匹配不构成错误证据",
            },
            "remaining_gap": analysis.get("remaining_gap"),
            "next_subgoal": state.current_task,
            "solution_status": analysis.get("solution_status", "in_progress"),
            "completion_evidence": analysis.get("completion_evidence"),
            "history_messages_submitted": analysis.get("history_messages_submitted", 0),
        }

    @staticmethod
    def _append_unique(items: list[str], values: list[str], limit: int) -> None:
        for value in values:
            normalized = value.strip()
            if normalized and normalized not in items:
                items.append(normalized)

    def _apply_context_analysis(
        self,
        record: SessionRecord,
        student_text: str,
        verdict: str,
        model_analysis: dict | None,
    ) -> None:
        analysis = model_analysis or {}
        self._append_unique(record.context.student_claims, [student_text], 10)
        new_evidence = analysis.get("new_evidence", [])
        if verdict in {"correct", "partially_correct"} and isinstance(new_evidence, list):
            self._append_unique(record.context.understanding_evidence, new_evidence, 20)
        if analysis.get("answers_current_question") and record.context.current_question:
            record.context.unresolved_questions = [
                item for item in record.context.unresolved_questions
                if item != record.context.current_question
            ]
        remaining_gap = analysis.get("remaining_gap")
        if isinstance(remaining_gap, str) and remaining_gap.strip():
            self._append_unique(record.context.unresolved_questions, [remaining_gap], 10)
        if analysis.get("self_correction_detected"):
            self._append_unique(record.context.understanding_evidence, ["学生主动修正了先前表达"], 20)

    def register_teacher_reply(self, session_id: str, speech: str) -> None:
        record = self.sessions[session_id]
        questions = re.findall(r"[^。！？!?]*[？?]", speech)
        if not questions:
            record.context.current_question_id = None
            record.context.current_question = None
            return
        question = questions[-1].strip()
        record.context.current_question_id = str(uuid4())
        record.context.current_question = question
        self._append_unique(record.context.recent_teacher_questions, [question], 5)
        self._append_unique(record.context.unresolved_questions, [question], 10)

    def build_policy(self, response: TutorTurnResponse) -> TeachingPolicy:
        state = response.state
        if response.intent == "challenge_ai":
            action = "review_challenge"
        elif response.intent == "request_answer":
            action = "redirect_from_answer"
        elif response.intent == "request_help" or response.verdict in {"incorrect", "unknown"}:
            action = "increase_hint"
        elif response.verdict == "partially_correct":
            action = "ask_clarification"
        elif state.phase == "complete":
            action = "finish_session"
        elif state.phase == "reflect":
            action = "ask_reflection"
        else:
            action = "acknowledge_and_ask_reason"

        allowed = [f"当前小任务：{state.current_task}"]
        if state.confirmed_steps:
            allowed.append("学生已经完成的步骤：" + "、".join(state.confirmed_steps[-2:]))
        record = self.sessions[state.session_id]
        if record.context.understanding_evidence:
            allowed.append("学生已经展示的理解：" + "、".join(record.context.understanding_evidence[-3:]))
        return TeachingPolicy(
            action=action,
            current_task=state.current_task,
            hint_level=state.hint_level,
            allowed_information=allowed,
            forbidden_information=[
                "最终答案或最终数值",
                "当前尚未完成的关键步骤",
                "后续完整解法或完整方程",
                "金标准内部答案",
            ],
            fallback_text=response.assistant_text,
        )

    def _hint(self, record: SessionRecord, index: int, level: int) -> str:
        steps = self._steps(record)
        step = steps[index] if index < len(steps) else None
        if not step:
            return "先不用计算。请找出题目中一个已知量和一个未知量，说说它们可能有什么关系。"
        goal = step.get("goal", "当前步骤")
        if level <= 2:
            return f"我们缩小范围，只考虑“{goal}”。题目里的哪个条件最直接相关？"
        operation = step.get("operation", "建立一个数量关系")
        if level == 3:
            return f"可以从“{operation}”这个方向想，但先由你说出关系，不急着计算。"
        return f"把任务拆小：先说出这一步等号左边和右边各表示什么。目标仍是“{goal}”。"

    @staticmethod
    def _judge(text: str, step: dict | None, gold_case: dict | None) -> str:
        if not step:
            return "unknown"
        evidence = " ".join([
            step.get("goal", ""), step.get("operation", ""),
            step.get("expression_after", "") or "",
        ])
        tokens = [token for token in re.findall(r"[\u4e00-\u9fff]{2,}|\d+|[xX]", evidence) if len(token) > 1 or token.isdigit()]
        hits = sum(1 for token in tokens if token in text)
        if hits >= 2 or any(key in text for key in ["速度和", "路程和", "单位一", "总数", "相差", "工作效率"]):
            return "correct"
        if hits == 1 or any(char.isdigit() for char in text):
            return "partially_correct"
        return "incorrect"
