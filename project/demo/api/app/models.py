from typing import Any, Literal

from pydantic import BaseModel, Field


class ImageRecognitionResult(BaseModel):
    raw_text: str
    normalized_display_text: str
    uncertain_spans: list[str] = []
    possible_multiple_problems: bool = False
    possible_truncation: bool = False
    confidence: float | None = None
    provider: str
    model: str


class ProblemConfirmRequest(BaseModel):
    confirmed_text: str = Field(min_length=4)


class ProblemObject(BaseModel):
    object_id: str
    name: str
    type: str
    value: Any = None
    unit: str | None = None
    role: str = "given"


class ProblemRelationship(BaseModel):
    relationship_id: str
    type: str
    natural_language: str
    expression: str = ""


class ConfirmedProblem(BaseModel):
    problem_id: str
    confirmed_text: str
    question: str = ""
    problem_type: str = "unknown"
    matched_case_id: str | None = None
    match_score: float
    objects: list[ProblemObject] = []
    relationships: list[ProblemRelationship] = []
    review_reasons: list[str] = []


class CreateSessionRequest(BaseModel):
    problem: ConfirmedProblem


class CompleteSessionRequest(BaseModel):
    trigger: Literal["student", "system"] = "student"


class CompletionSummary(BaseModel):
    title: str = "这道题的解题思路"
    method: str
    key_relationship: str
    steps: list[str] = []
    common_pitfall: str | None = None
    closing_message: str
    trigger: Literal["student", "system"]


class StudentReasoningNode(BaseModel):
    node_id: str
    claim: str
    normalized_math: str | None = None
    evidence: str
    verification_status: Literal["verified", "partially_verified", "rejected", "unverified"]
    depends_on: list[str] = []
    reference_step_id: str | None = None


class SessionState(BaseModel):
    session_id: str
    phase: Literal["orient", "attempt", "reflect", "transfer", "complete"]
    current_step_index: int = 0
    active_path_id: str | None = None
    completed_step_ids: list[str] = []
    frontier_step_ids: list[str] = []
    candidate_step_ids: list[str] = []
    thought_alignment: Literal[
        "aligned", "jumped_ahead", "alternative_path", "new_valid_path", "ambiguous", "unknown"
    ] = "unknown"
    thought_confidence: float = 0.0
    student_method_summary: str | None = None
    reasoning_nodes: list[StudentReasoningNode] = []
    completion_summary: CompletionSummary | None = None
    hint_level: int = 1
    turn_count: int = 0
    confirmed_steps: list[str] = []
    current_task: str
    problem: ConfirmedProblem


class TutorContext(BaseModel):
    current_question_id: str | None = None
    current_question: str | None = None
    understanding_evidence: list[str] = []
    unresolved_questions: list[str] = []
    misconceptions: list[str] = []
    student_claims: list[str] = []
    recent_teacher_questions: list[str] = []
    pending_incomplete_utterance: str | None = None


class TurnRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)


class BlackboardPatch(BaseModel):
    current_task: str
    focus_objects: list[str] = []
    relation: str | None = None
    confirmed_steps: list[str] = []


class TeachingPolicy(BaseModel):
    action: Literal[
        "acknowledge_and_ask_reason",
        "ask_clarification",
        "increase_hint",
        "redirect_from_answer",
        "review_challenge",
        "ask_reflection",
        "finish_session",
    ]
    current_task: str
    hint_level: int
    allowed_information: list[str] = []
    forbidden_information: list[str] = []
    fallback_text: str


class GeneratedTutorReply(BaseModel):
    speech: str = Field(min_length=2, max_length=300)
    caption: str = Field(min_length=2, max_length=300)
    blackboard_focus_objects: list[str] = []
    blackboard_relation: str | None = None


class TutorTurnResponse(BaseModel):
    turn_id: str
    student_text: str
    intent: str
    verdict: Literal["correct", "partially_correct", "incorrect", "unknown"]
    assistant_text: str
    caption: str
    should_speak: bool = True
    state: SessionState
    blackboard: BlackboardPatch
    guard: dict[str, Any]
    business_trace: dict[str, Any] = {}


class TranscriptResult(BaseModel):
    raw_text: str
    display_text: str
    uncertain_tokens: list[str] = []
    requires_confirmation: bool = False
    provider: str
    model: str
