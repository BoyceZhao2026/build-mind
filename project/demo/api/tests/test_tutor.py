from app.gold_cases import GoldCaseRepository
from app.adapters import FunASRAdapter
from app.models import CompletionSummary, ConfirmedProblem, ProblemObject
from app.models import GeneratedTutorReply
from app.response_generator import GuidedResponseGenerator
from app.completion_summary import CompletionSummaryGenerator
from app.tutor import TutorEngine


def test_answer_request_is_redirected_without_answer():
    engine = TutorEngine()
    problem = ConfirmedProblem(
        problem_id="p1",
        confirmed_text="测试题",
        match_score=0,
        objects=[ProblemObject(object_id="total", name="总数", type="amount")],
    )
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "直接告诉我答案")
    assert "不直接给" in response.assistant_text
    assert response.intent == "request_answer"


def test_gold_repository_loads_seed_cases(tmp_path):
    path = tmp_path / "cases.yaml"
    path.write_text("cases:\n  - case_id: c1\n    problem:\n      text: 一道测试题\n", encoding="utf-8")
    repository = GoldCaseRepository(path)
    case, score = repository.best_match("一道测试题")
    assert case["case_id"] == "c1"
    assert score == 1


def test_fun_asr_extracts_text_from_sentence_list():
    payload = [
        {"sentence_id": 1, "text": "我觉得应该先算速度和。"},
        {"sentence_id": 2, "text": "然后再看总路程。"},
    ]
    assert FunASRAdapter._extract_text(payload) == "我觉得应该先算速度和。然后再看总路程。"


def test_policy_redirects_answer_request():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="p2", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "答案是多少")
    policy = engine.build_policy(response)
    assert policy.action == "redirect_from_answer"
    assert "最终答案或最终数值" in policy.forbidden_information


def test_generated_reply_guard_blocks_final_answer():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="p3", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "我想先找关系")
    generator = GuidedResponseGenerator(None)  # type: ignore[arg-type]
    candidate = GeneratedTutorReply(
        speech="最终答案是3。",
        caption="答案是3",
        blackboard_focus_objects=[],
    )
    violations = generator._guard(candidate, response, 3)
    assert "final_answer_number" in violations
    assert "explicit_answer_phrase" in violations


def test_context_tracks_answered_question_and_evidence():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="p4", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    engine.respond(state.session_id, "总数是84", model_analysis={
        "intent": "attempt",
        "verdict": "partially_correct",
        "answers_current_question": True,
        "new_evidence": ["学生识别出总数是84"],
        "remaining_gap": "还没有建立数量关系",
    })
    snapshot = engine.context_snapshot(state.session_id)
    assert "学生识别出总数是84" in snapshot["understanding_evidence"]
    assert "你目前有什么想法？" not in snapshot["unresolved_questions"]
    assert "还没有建立数量关系" in snapshot["unresolved_questions"]


def test_generated_reply_guard_blocks_repeated_question():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="p5", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "我还不知道")
    generator = GuidedResponseGenerator(None)  # type: ignore[arg-type]
    candidate = GeneratedTutorReply(
        speech="你目前有什么想法？",
        caption="你有什么想法？",
        blackboard_focus_objects=[],
    )
    violations = generator._guard(candidate, response, None, {
        "recent_teacher_questions": ["你目前有什么想法？"],
    })
    assert "repeated_question" in violations


def test_generated_reply_guard_allows_only_one_question():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="p6", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "我有一点想法")
    generator = GuidedResponseGenerator(None)  # type: ignore[arg-type]
    candidate = GeneratedTutorReply(
        speech="你找到了哪个条件？准备怎么列式？",
        caption="说说你的列式思路",
        blackboard_focus_objects=[],
    )
    assert "too_many_questions" in generator._guard(candidate, response, None, {})


def _dynamic_gold_case():
    return {
        "solution_paths": [
            {
                "path_id": "equation",
                "method": "方程法",
                "steps": [
                    {"step_id": "e1", "depends_on": [], "goal": "表示两个未知量", "operation": "设较小量为x"},
                    {"step_id": "e2", "depends_on": ["e1"], "goal": "建立总量方程", "operation": "两个量之和等于总量"},
                    {"step_id": "e3", "depends_on": ["e2"], "goal": "解方程", "operation": "求出x"},
                ],
            },
            {
                "path_id": "arithmetic",
                "method": "算术法",
                "steps": [
                    {"step_id": "a1", "depends_on": [], "goal": "从总量中去掉差", "operation": "总量减去相差数"},
                    {"step_id": "a2", "depends_on": ["a1"], "goal": "求较小量", "operation": "平均分成两份"},
                ],
            },
        ]
    }


def test_dynamic_thought_can_cover_multiple_steps_in_one_turn():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="dynamic-1", confirmed_text="两种书共84本，相差18本", match_score=1)
    state = engine.create_session(problem, _dynamic_gold_case())
    response = engine.respond(state.session_id, "设故事书为x，科技书是x加18，所以x加x加18等于84", {
        "intent": "attempt",
        "verdict": "correct",
        "alignment": "jumped_ahead",
        "selected_path_id": "equation",
        "selected_step_id": "e2",
        "covered_step_ids": ["e1", "e2"],
        "step_candidates": [
            {"step_id": "e2", "score": 0.98, "evidence": "x加x加18等于84"},
            {"step_id": "e1", "score": 0.92, "evidence": "设故事书为x"},
        ],
        "confidence": 0.98,
        "new_evidence": ["学生能定义未知量并建立方程"],
    })
    assert response.state.completed_step_ids == ["e1", "e2"]
    assert response.state.frontier_step_ids == ["e3", "a1"]
    assert response.state.current_task == "解方程"
    assert response.state.thought_alignment == "jumped_ahead"
    assert response.state.candidate_step_ids == ["e2", "e1"]


def test_dynamic_thought_switches_to_an_alternative_reference_path():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="dynamic-2", confirmed_text="两种书共84本，相差18本", match_score=1)
    state = engine.create_session(problem, _dynamic_gold_case())
    response = engine.respond(state.session_id, "我想先用84减18，再把剩下的平均分", {
        "intent": "attempt",
        "verdict": "correct",
        "alignment": "alternative_path",
        "selected_path_id": "arithmetic",
        "selected_step_id": "a1",
        "covered_step_ids": ["a1"],
        "step_candidates": [{"step_id": "a1", "score": 0.96, "evidence": "84减18"}],
        "confidence": 0.96,
        "new_evidence": ["学生选择算术法去掉相差量"],
    })
    assert response.state.active_path_id == "arithmetic"
    assert response.state.current_task == "求较小量"
    assert "a2" in response.state.frontier_step_ids


def test_unverified_new_path_does_not_advance_graph():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="dynamic-3", confirmed_text="测试题", match_score=1)
    state = engine.create_session(problem, _dynamic_gold_case())
    response = engine.respond(state.session_id, "我有另外一种画图方法", {
        "intent": "attempt",
        "verdict": "unknown",
        "alignment": "new_valid_path",
        "selected_path_id": None,
        "selected_step_id": None,
        "covered_step_ids": [],
        "step_candidates": [],
        "confidence": 0.45,
        "remaining_gap": "还没有说明图中的数量关系",
    })
    assert response.state.completed_step_ids == []
    assert response.state.active_path_id is None
    assert response.state.thought_alignment == "new_valid_path"


def test_context_submits_complete_conversation_history():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="history", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    for index in range(5):
        engine.respond(state.session_id, f"第{index + 1}次回答")
    snapshot = engine.context_snapshot(state.session_id)
    assert len(snapshot["conversation_history"]) == 10
    assert snapshot["conversation_history"][0]["text"] == "第1次回答"
    assert snapshot["conversation_history"][-2]["text"] == "第5次回答"


def test_reasoning_graph_advances_without_gold_step_match():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="open-path", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "我先画一条线段表示总量", {
        "intent": "attempt",
        "verdict": "correct",
        "alignment": "new_valid_path",
        "selected_path_id": None,
        "selected_step_id": None,
        "covered_step_ids": [],
        "step_candidates": [],
        "student_method_summary": "使用线段图表示数量关系",
        "confidence": 0.91,
        "next_subgoal": "在线段图中标出相差的部分",
        "reasoning_nodes": [{
            "node_id": "turn_1",
            "claim": "用线段表示总量",
            "normalized_math": None,
            "evidence": "先画一条线段表示总量",
            "verification_status": "verified",
            "depends_on": [],
            "reference_step_id": None,
        }],
    })
    assert response.state.current_task == "在线段图中标出相差的部分"
    assert response.state.reasoning_nodes[0].reference_step_id is None
    assert response.business_trace["reasoning_graph"][0]["claim"] == "用线段表示总量"


def test_solved_answer_enters_reflection_before_completion():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="finish-1", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "我已经算完并检验了", {
        "intent": "attempt", "verdict": "correct", "alignment": "aligned", "confidence": 0.95,
        "solution_status": "solved", "completion_evidence": "学生完成计算和检验",
        "next_subgoal": "", "reasoning_nodes": [], "step_candidates": [], "covered_step_ids": [],
    })
    assert response.state.phase == "reflect"
    assert response.state.current_task == "用自己的话说明解题中的关键数量关系"
    assert "结束前" in response.assistant_text


def test_understanding_verified_enters_complete_state():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="finish-2", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    state.phase = "reflect"
    response = engine.respond(state.session_id, "关键关系是两个部分合起来等于总量", {
        "intent": "attempt", "verdict": "correct", "alignment": "aligned", "confidence": 0.98,
        "solution_status": "understanding_verified", "completion_evidence": "学生解释了关键关系",
        "next_subgoal": "", "reasoning_nodes": [], "step_candidates": [], "covered_step_ids": [],
    })
    assert response.state.phase == "complete"
    assert response.state.current_task == "本题辅导已完成"
    assert engine.build_policy(response).action == "finish_session"
    assert "结束" in response.assistant_text


def test_legacy_no_next_task_text_is_treated_as_solved():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="finish-3", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    response = engine.respond(state.session_id, "完成了", {
        "intent": "attempt", "verdict": "correct", "next_subgoal": "无（当前小任务已完成）",
    })
    assert response.state.phase == "reflect"
    assert "无（当前小任务已完成）" not in response.assistant_text


def test_student_can_explicitly_complete_session():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="manual-finish", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    completed = engine.complete_session(state.session_id)
    assert completed.phase == "complete"
    assert completed.current_task == "本题辅导已完成"


def test_completion_summary_fallback_uses_student_reasoning():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="summary", confirmed_text="测试题", match_score=0)
    state = engine.create_session(problem, None)
    engine.respond(state.session_id, "先找总量关系", {
        "intent": "attempt", "verdict": "correct", "alignment": "aligned", "confidence": 0.9,
        "student_method_summary": "先建立总量关系",
        "next_subgoal": "继续计算", "reasoning_nodes": [{
            "node_id": "turn_1", "claim": "两个部分合起来等于总量", "normalized_math": "a+b=total",
            "evidence": "先找总量关系", "verification_status": "verified", "depends_on": [], "reference_step_id": None,
        }], "step_candidates": [], "covered_step_ids": [],
    })
    summary = CompletionSummaryGenerator._fallback(engine.sessions[state.session_id], "student")
    assert summary.trigger == "student"
    assert summary.method == "先建立总量关系"
    assert summary.steps == ["两个部分合起来等于总量"]
    assert summary.key_relationship == "a+b=total"


def test_completion_summary_guard_removes_answer_and_new_task():
    engine = TutorEngine()
    problem = ConfirmedProblem(problem_id="summary-guard", confirmed_text="测试题", match_score=1)
    state = engine.create_session(problem, {"answer": {"final_value": {"a": 33, "b": 51}}})
    candidate = CompletionSummary(
        method="线段图法",
        key_relationship="两个部分合起来等于总量",
        steps=["先画两条线段", "算出故事书是33本"],
        common_pitfall=None,
        closing_message="下一步你可以试试算出51吗？",
        trigger="student",
    )
    summary = CompletionSummaryGenerator._sanitize(candidate, engine.sessions[state.session_id])
    assert summary.steps == ["先画两条线段"]
    assert "下一步" not in summary.closing_message
    assert "？" not in summary.closing_message
    assert "51" not in summary.closing_message
