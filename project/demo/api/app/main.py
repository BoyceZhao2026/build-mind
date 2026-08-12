import io
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageOps

from .adapters import build_adapters
from .completion_summary import CompletionSummaryGenerator
from .gold_cases import GoldCaseRepository
from .geometry_models import ValidateSplitRequest, ValidateSplitResponse
from .geometry_rules import GeometryReasoner
from .llm import LLMRequest, build_llm_registry
from .models import (
    ConfirmedProblem,
    CompleteSessionRequest,
    CreateSessionRequest,
    ProblemConfirmRequest,
    ProblemObject,
    ProblemRelationship,
    TurnRequest,
)
from .response_generator import GuidedResponseGenerator
from .settings import configure_process_proxy, get_settings
from .tutor import TutorEngine

settings = get_settings()
configure_process_proxy(settings)
repository = GoldCaseRepository(settings.gold_path)
vision, stt, tts = build_adapters(settings)
tutor = TutorEngine()
llm_registry = build_llm_registry(settings)
response_generator = (
    GuidedResponseGenerator(llm_registry.get("tutor_primary"))
    if "tutor_primary" in llm_registry.profiles
    else None
)
completion_summary_generator = CompletionSummaryGenerator(
    llm_registry.get("tutor_primary") if "tutor_primary" in llm_registry.profiles else None
)
geometry_reasoner = GeometryReasoner()

app = FastAPI(title="引导式 AI 家教 Demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "mode": settings.demo_mode, "gold_cases": len(repository.cases)}


@app.get("/api/cases")
def list_cases():
    return repository.public_cases()


@app.get("/api/models")
def list_models():
    return {
        "mode": settings.demo_mode,
        "llm_profiles": llm_registry.profiles,
        "vision": settings.qwen_vision_model,
        "stt": settings.fun_asr_model,
        "tts": settings.cosyvoice_model,
    }


@app.post("/api/problems/recognize")
async def recognize_problem(image: UploadFile = File(...)):
    content_type = image.content_type or "application/octet-stream"
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "只支持 JPEG、PNG 或 WebP 图片")
    payload = await image.read()
    if len(payload) > 10 * 1024 * 1024:
        raise HTTPException(413, "图片不能超过 10MB")
    try:
        with Image.open(io.BytesIO(payload)) as source:
            normalized = ImageOps.exif_transpose(source)
            width, height = normalized.size
            if width * height > 24_000_000:
                raise HTTPException(400, "图片像素过大，请压缩或裁剪后重试")
            if min(width, height) < 240:
                raise HTTPException(400, "图片尺寸过小，可能无法准确识别")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, "图片无法解码") from exc
    return await vision.recognize(payload, content_type)


@app.post("/api/problems/confirm", response_model=ConfirmedProblem)
async def confirm_problem(request: ProblemConfirmRequest):
    case, score = repository.best_match(request.confirmed_text)
    if case:
        objects = [ProblemObject(**obj) for obj in case.get("objects", [])]
        relationships = [ProblemRelationship(**rel) for rel in case.get("relationships", [])]
        return ConfirmedProblem(
            problem_id=str(uuid4()),
            confirmed_text=request.confirmed_text,
            question=case.get("problem", {}).get("question", ""),
            problem_type=case.get("scope", {}).get("problem_type", "unknown"),
            matched_case_id=case.get("case_id"),
            match_score=score,
            objects=objects,
            relationships=relationships,
        )
    return ConfirmedProblem(
        problem_id=str(uuid4()),
        confirmed_text=request.confirmed_text,
        match_score=score,
        review_reasons=["gold_case_not_found", "math_verification_unknown"],
    )


@app.post("/api/geometry/validate-split", response_model=ValidateSplitResponse)
def validate_geometry_split(request: ValidateSplitRequest):
    """Validate a student-confirmed helper line against an already confirmed diagram."""
    return geometry_reasoner.validate_rectangle_partition(request)


@app.post("/api/sessions")
def create_session(request: CreateSessionRequest):
    case = next(
        (item for item in repository.cases if item.get("case_id") == request.problem.matched_case_id),
        None,
    )
    return tutor.create_session(request.problem, case)


@app.post("/api/sessions/{session_id}/turn")
async def submit_turn(session_id: str, request: TurnRequest):
    if session_id not in tutor.sessions:
        raise HTTPException(404, "辅导会话不存在")
    model_analysis = None
    if "tutor_primary" in llm_registry.profiles:
        record = tutor.sessions[session_id]
        conversation_context = tutor.context_snapshot(session_id)
        try:
            result = await llm_registry.get("tutor_primary").generate(LLMRequest(
                task="student_step_analysis",
                trace_id=str(uuid4()),
                temperature=0,
                response_schema={
                    "type": "object",
                    "properties": {
                        "intent": {"enum": ["attempt", "request_help", "request_answer", "challenge_ai"]},
                        "verdict": {"enum": ["correct", "partially_correct", "incorrect", "unknown"]},
                        "evidence": {"type": "string"},
                        "answers_current_question": {"type": "boolean"},
                        "current_question_id": {"type": ["string", "null"]},
                        "new_evidence": {"type": "array", "items": {"type": "string"}},
                        "referenced_prior_turns": {"type": "array", "items": {"type": "string"}},
                        "remaining_gap": {"type": ["string", "null"]},
                        "self_correction_detected": {"type": "boolean"},
                        "alignment": {"enum": ["aligned", "jumped_ahead", "alternative_path", "new_valid_path", "ambiguous", "unknown"]},
                        "selected_path_id": {"type": ["string", "null"]},
                        "selected_step_id": {"type": ["string", "null"]},
                        "covered_step_ids": {"type": "array", "items": {"type": "string"}},
                        "step_candidates": {"type": "array", "items": {"type": "object", "properties": {"step_id": {"type": "string"}, "score": {"type": "number"}, "evidence": {"type": "string"}}, "required": ["step_id", "score", "evidence"]}},
                        "student_method_summary": {"type": "string"},
                        "confidence": {"type": "number"},
                        "reasoning_nodes": {"type": "array", "items": {"type": "object", "properties": {
                            "node_id": {"type": "string"},
                            "claim": {"type": "string"},
                            "normalized_math": {"type": ["string", "null"]},
                            "evidence": {"type": "string"},
                            "verification_status": {"enum": ["verified", "partially_verified", "rejected", "unverified"]},
                            "depends_on": {"type": "array", "items": {"type": "string"}},
                            "reference_step_id": {"type": ["string", "null"]}
                        }, "required": ["node_id", "claim", "normalized_math", "evidence", "verification_status", "depends_on", "reference_step_id"]}},
                        "next_subgoal": {"type": "string"},
                        "validation_basis": {"type": "string"},
                        "solution_status": {"enum": ["in_progress", "solved", "understanding_verified"]},
                        "completion_evidence": {"type": ["string", "null"]},
                    },
                    "required": [
                        "intent", "verdict", "evidence", "answers_current_question",
                        "current_question_id", "new_evidence", "referenced_prior_turns",
                        "remaining_gap", "self_correction_detected",
                        "alignment", "selected_path_id", "selected_step_id", "covered_step_ids",
                        "step_candidates", "student_method_summary", "confidence",
                        "reasoning_nodes", "next_subgoal", "validation_basis",
                        "solution_status", "completion_evidence",
                    ],
                },
                system_prompt=(
                    "你负责根据题目事实和完整对话，独立理解六年级学生正在形成的解题思路。"
                    "输入不会提供标准解法；不要假设存在唯一顺序，也不要为了贴合某种常见方法而补写学生没说的内容。"
                    "reasoning_nodes只记录学生本轮实际表达的数学主张，每个节点必须引用原话证据并给出局部验证状态；"
                    "node_id使用turn_加本轮序号，例如turn_1。depends_on只能引用输入中已有推理节点或本轮更早节点。"
                    "reference_step_id、selected_path_id、selected_step_id保持null，step_candidates和covered_step_ids保持空数组；在线判断不依赖金标准。"
                    "alignment依据学生自己的推理连续性判断：承接已有节点为aligned，跳过依据为jumped_ahead，明显换方法为alternative_path，"
                    "提出尚未收录的新思路为new_valid_path，无法辨认为ambiguous或unknown。"
                    "verdict=correct仅当本轮数学主张可由题目事实或已验证节点支持；结论正确但理由缺失最多partially_correct。"
                    "solution_status=in_progress表示仍有必要解题步骤；solved表示学生已经独立得到并说明完整解答，但还需要理解复述；"
                    "understanding_verified仅当学生已完成解答，并进一步正确解释关键关系或通过理解检验。"
                    "如果solution_status不是in_progress，next_subgoal必须返回空字符串，禁止返回‘无’、‘已完成’等伪任务。"
                    "只复述题目条件、只提到相关对象、方向相关但缺少关键关系时，最多判 partially_correct；"
                    "与当前步骤无关或关系错误判 incorrect；证据不足判 unknown。"
                    "evidence 必须引用学生原话中的短语，不能用参考步骤替学生补全。"
                    "结合 current_question 和 recent_turns 判断学生是否回答了上一问；"
                    "new_evidence 只能记录学生本轮真正表现出的理解，remaining_gap 只写尚缺的一点。"
                    "不要解题，不要输出答案，不要评价后续步骤，只输出JSON。"
                ),
                user_prompt=(
                    f"题目：{record.state.problem.confirmed_text}\n"
                    f"当前小任务：{record.state.current_task}\n"
                    f"学生动态推理图：{[node.model_dump() for node in record.state.reasoning_nodes]}\n"
                    f"对话上下文：{conversation_context}\n"
                    f"学生表达：{request.text.strip()}"
                ),
            ))
            model_analysis = result.parsed
            if isinstance(model_analysis, dict):
                model_analysis["history_messages_submitted"] = len(conversation_context.get("conversation_history", []))
        except Exception:
            model_analysis = None
    response = tutor.respond(session_id, request.text.strip(), model_analysis=model_analysis)
    if response_generator is not None:
        record = tutor.sessions[session_id]
        policy = tutor.build_policy(response)
        response.business_trace["teaching_action"] = policy.action
        response.business_trace["allowed_information"] = policy.allowed_information
        final_answer = (record.gold_case or {}).get("answer", {}).get("final_value")
        candidate, guard = await response_generator.generate(
            response=response,
            policy=policy,
            student_text=request.text.strip(),
            final_answer=final_answer,
            conversation_context=tutor.context_snapshot(session_id, include_latest_turn=False),
        )
        guard["thought_analysis"] = {
            "alignment": response.state.thought_alignment,
            "confidence": response.state.thought_confidence,
            "candidate_step_ids": response.state.candidate_step_ids,
            "completed_step_ids": response.state.completed_step_ids,
            "frontier_step_ids": response.state.frontier_step_ids,
            "active_path_id": response.state.active_path_id,
        }
        response.guard = guard
        response.business_trace["guard"] = {
            "decision": guard.get("decision"),
            "violations": guard.get("violations", []),
            "leakage_safe": guard.get("leakage_safe"),
        }
        if candidate is not None:
            known_names = {obj.name for obj in response.state.problem.objects}
            response.assistant_text = candidate.speech
            response.caption = candidate.caption
            response.blackboard.focus_objects = [
                name for name in candidate.blackboard_focus_objects if name in known_names
            ][:4]
            response.blackboard.relation = candidate.blackboard_relation
    if response.state.phase == "complete" and response.state.completion_summary is None:
        summary = await completion_summary_generator.generate(tutor.sessions[session_id], "system")
        response.state.completion_summary = summary
        response.business_trace["completion_summary_generated"] = True
    tutor.register_teacher_reply(session_id, response.assistant_text)
    return response


@app.post("/api/sessions/{session_id}/complete")
async def complete_session(session_id: str, request: CompleteSessionRequest):
    if session_id not in tutor.sessions:
        raise HTTPException(404, "辅导会话不存在")
    record = tutor.sessions[session_id]
    tutor.complete_session(session_id)
    if record.state.completion_summary is None:
        record.state.completion_summary = await completion_summary_generator.generate(record, request.trigger)
    assistant_text = "好的，既然你已经理解了，我们就完成这道题。我把刚才的解题思路整理在总结卡片里。"
    return {
        "state": record.state,
        "summary": record.state.completion_summary,
        "assistant_text": assistant_text,
        "trigger": request.trigger,
    }


@app.post("/api/speech/transcribe")
async def transcribe(audio: UploadFile = File(...)):
    payload = await audio.read()
    if not payload:
        raise HTTPException(400, "录音为空")
    suffix = Path(audio.filename or "recording.webm").suffix.lower()
    return await stt.transcribe(payload, suffix)


@app.post("/api/speech/synthesize")
async def synthesize(request: TurnRequest):
    if tts is None:
        raise HTTPException(501, "Mock 模式使用浏览器 SpeechSynthesis 朗读")
    audio, media_type = await tts.synthesize(request.text)
    return Response(content=audio, media_type=media_type)
