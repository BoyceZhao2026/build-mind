import json
import time
from abc import ABC, abstractmethod
from typing import Any

import httpx
from openai import AsyncOpenAI
from pydantic import BaseModel

from .settings import Settings
from .telemetry import append_model_call


class LLMRequest(BaseModel):
    task: str
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any] | None = None
    temperature: float = 0.0
    trace_id: str


class LLMResult(BaseModel):
    provider: str
    model: str
    content: str
    parsed: dict[str, Any] | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    latency_ms: int


class LLMAdapter(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResult: ...


class OpenAICompatibleLLM(LLMAdapter):
    """所有兼容 OpenAI Chat Completions 的模型共用这一实现。"""

    def __init__(self, provider: str, model: str, api_key: str, base_url: str):
        self.provider = provider
        self.model = model
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            http_client=httpx.AsyncClient(trust_env=False),
        )

    async def generate(self, request: LLMRequest) -> LLMResult:
        started = time.perf_counter()
        system_prompt = request.system_prompt
        if request.response_schema:
            system_prompt += (
                "\n你必须只返回一个JSON对象，并严格使用下面JSON Schema中的字段名、类型和枚举值；"
                "不要增加解释、Markdown或Schema外字段：\n"
                + json.dumps(request.response_schema, ensure_ascii=False, separators=(",", ":"))
            )
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=request.temperature,
                response_format={"type": "json_object"} if request.response_schema else None,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": request.user_prompt},
                ],
            )
        except Exception as exc:
            append_model_call({
                "trace_id": request.trace_id,
                "task": request.task,
                "provider": self.provider,
                "model": self.model,
                "status": "error",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__,
            })
            raise
        content = response.choices[0].message.content or ""
        parsed = json.loads(content) if request.response_schema else None
        usage = response.usage
        result = LLMResult(
            provider=self.provider,
            model=self.model,
            content=content,
            parsed=parsed,
            input_tokens=usage.prompt_tokens if usage else None,
            output_tokens=usage.completion_tokens if usage else None,
            latency_ms=round((time.perf_counter() - started) * 1000),
        )
        append_model_call({
            "trace_id": request.trace_id,
            "task": request.task,
            "provider": result.provider,
            "model": result.model,
            "status": "success",
            "latency_ms": result.latency_ms,
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
        })
        return result


class LLMRegistry:
    def __init__(self):
        self._profiles: dict[str, LLMAdapter] = {}

    def register(self, profile: str, adapter: LLMAdapter) -> None:
        self._profiles[profile] = adapter

    def get(self, profile: str) -> LLMAdapter:
        if profile not in self._profiles:
            raise KeyError(f"LLM profile not configured: {profile}")
        return self._profiles[profile]

    @property
    def profiles(self) -> list[str]:
        return sorted(self._profiles)


def build_llm_registry(settings: Settings) -> LLMRegistry:
    registry = LLMRegistry()
    if settings.demo_mode == "aliyun" and settings.dashscope_api_key:
        registry.register(
            "tutor_primary",
            OpenAICompatibleLLM(
                provider="aliyun",
                model=settings.qwen_llm_model,
                api_key=settings.dashscope_api_key,
                base_url=settings.openai_base_url,
            ),
        )
    return registry
