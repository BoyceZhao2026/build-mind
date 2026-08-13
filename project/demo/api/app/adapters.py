import base64
import json
import os
import tempfile
import time
from abc import ABC, abstractmethod
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from .models import ImageRecognitionResult, TranscriptResult
from .settings import Settings
from .telemetry import append_model_call


class VisionAdapter(ABC):
    @abstractmethod
    async def recognize(self, image: bytes, mime_type: str) -> ImageRecognitionResult: ...


class MockVisionAdapter(VisionAdapter):
    async def recognize(self, image: bytes, mime_type: str) -> ImageRecognitionResult:
        text = "甲、乙两人同时从相距360米的两地相向而行。甲每分钟走50米，乙每分钟走70米。几分钟后两人相遇？"
        return ImageRecognitionResult(
            raw_text=text,
            normalized_display_text=text,
            confidence=1.0,
            provider="mock",
            model="seed-case",
        )


class QwenVisionAdapter(VisionAdapter):
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = AsyncOpenAI(
            api_key=settings.dashscope_api_key,
            base_url=settings.openai_base_url,
            http_client=httpx.AsyncClient(trust_env=False),
        )

    async def recognize(self, image: bytes, mime_type: str) -> ImageRecognitionResult:
        started = time.perf_counter()
        encoded = base64.b64encode(image).decode("ascii")
        try:
            response = await self.client.chat.completions.create(
                model=self.settings.qwen_vision_model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                        {"type": "text", "text": (
                            "忠实转写图片中的一道中文数学应用题，不要解题，不要补条件，不要改数字。"
                            "输出JSON：raw_text、normalized_display_text、uncertain_spans字符串数组、"
                            "possible_multiple_problems布尔值、possible_truncation布尔值、confidence数值、diagram_graph。"
                            "如果题目不依赖图形，diagram_graph为null。否则diagram_graph包含：schema_version='1.0'、"
                            "diagram_id、diagram_type(只能是geometry/segment_model/motion/statistics/other；方格图也必须写geometry，不能写grid)、confidence、status='draft'、"
                            "entities数组、relations数组、uncertainties数组。entities每项包含entity_id、type(point/segment/circle/arc/polygon/region/text_label/measurement_label/symbol_marker)、"
                            "label、geometry(使用0到1归一化坐标)、confidence、status(candidate/needs_confirmation)。"
                            "relations每项包含relation_id、predicate、subjects、value、source(problem_text/explicit_diagram_mark/model_inferred)、confidence、status；"
                            "value必须是JSON对象或null，例如{\"pattern\":\"grid\"}，不能直接返回字符串。"
                            "如果是网格面积题：网格region的geometry必须包含grid:{columns整数,rows整数,cell_area:{number数值,unit字符串}}；"
                            "目标polygon的geometry必须包含coordinate_space='grid'和grid_vertices，每个顶点必须是对应网格交点的[x,y]坐标；"
                            "不要只返回图片归一化顶点。网格线数量和顶点位置无法确定时加入uncertainties，禁止猜测。"
                            "predicate只能使用is_triangle/is_rectangle/is_square/is_parallelogram/is_trapezoid/is_circle/is_semicircle/is_sector/"
                            "endpoint_of/boundary_edge/inside/contains/intersects/disjoint/overlaps/composed_of/parallel/perpendicular/equal_length/collinear/tangent/adjacent/shares_boundary/"
                            "length/angle_measure/radius/diameter/perimeter/area/disjoint_union/region_difference/equal_area/split_into/rearranged_to。"
                            "只根据外观看出的平行、垂直、等长必须标记model_inferred和needs_confirmation，不能当作已确认事实。"
                        )},
                    ],
                }],
            )
        except Exception as exc:
            append_model_call({
                "task": "image_recognition", "provider": "aliyun",
                "model": self.settings.qwen_vision_model, "status": "error",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__,
            })
            raise
        payload = json.loads(response.choices[0].message.content or "{}")
        result = ImageRecognitionResult(
            **payload,
            provider="aliyun",
            model=self.settings.qwen_vision_model,
        )
        append_model_call({
            "task": "image_recognition", "provider": "aliyun",
            "model": self.settings.qwen_vision_model, "status": "success",
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
        return result


class STTAdapter(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes, suffix: str) -> TranscriptResult: ...


class MockSTTAdapter(STTAdapter):
    async def transcribe(self, audio: bytes, suffix: str) -> TranscriptResult:
        text = "我觉得应该先把两个人每分钟走的路程合起来。"
        return TranscriptResult(
            raw_text=text,
            display_text=text,
            provider="mock",
            model="mock-stt",
        )


class FunASRAdapter(STTAdapter):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def transcribe(self, audio: bytes, suffix: str) -> TranscriptResult:
        import asyncio
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(self._transcribe_sync, audio, suffix)
        except Exception as exc:
            append_model_call({
                "task": "speech_recognition", "provider": "aliyun",
                "model": self.settings.fun_asr_model, "status": "error",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__,
            })
            raise
        append_model_call({
            "task": "speech_recognition", "provider": "aliyun",
            "model": self.settings.fun_asr_model, "status": "success",
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
        return result

    def _transcribe_sync(self, audio: bytes, suffix: str) -> TranscriptResult:
        import dashscope
        from dashscope.audio.asr import Recognition

        dashscope.api_key = self.settings.dashscope_api_key
        dashscope.base_websocket_api_url = self.settings.websocket_base_url
        safe_suffix = suffix if suffix in {".wav", ".mp3", ".m4a", ".webm", ".ogg"} else ".webm"
        with tempfile.NamedTemporaryFile(suffix=safe_suffix, delete=False) as file:
            file.write(audio)
            temp_path = file.name
        try:
            recognition = Recognition(
                model=self.settings.fun_asr_model,
                format=safe_suffix.lstrip("."),
                sample_rate=16000,
                callback=None,
            )
            result = recognition.call(temp_path)
            sentence = result.get_sentence() or {}
            text = self._extract_text(sentence)
            if not text:
                raise RuntimeError(getattr(result, "message", "语音识别没有返回文本"))
            return TranscriptResult(
                raw_text=text,
                display_text=text,
                provider="aliyun",
                model=self.settings.fun_asr_model,
            )
        finally:
            Path(temp_path).unlink(missing_ok=True)

    @staticmethod
    def _extract_text(sentence: object) -> str:
        if isinstance(sentence, list):
            return "".join(
                str(item.get("text", ""))
                for item in sentence
                if isinstance(item, dict) and item.get("text")
            ).strip()
        if isinstance(sentence, dict):
            if sentence.get("text"):
                return str(sentence["text"]).strip()
            nested = sentence.get("sentences")
            if isinstance(nested, list):
                return "".join(
                    str(item.get("text", ""))
                    for item in nested
                    if isinstance(item, dict) and item.get("text")
                ).strip()
        return ""


class TTSAdapter(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> tuple[bytes, str]: ...


class CosyVoiceAdapter(TTSAdapter):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def synthesize(self, text: str) -> tuple[bytes, str]:
        import asyncio
        started = time.perf_counter()
        try:
            result = await asyncio.to_thread(self._synthesize_sync, text)
        except Exception as exc:
            append_model_call({
                "task": "speech_synthesis", "provider": "aliyun",
                "model": self.settings.cosyvoice_model, "status": "error",
                "latency_ms": round((time.perf_counter() - started) * 1000),
                "error_type": type(exc).__name__,
            })
            raise
        append_model_call({
            "task": "speech_synthesis", "provider": "aliyun",
            "model": self.settings.cosyvoice_model, "status": "success",
            "latency_ms": round((time.perf_counter() - started) * 1000),
        })
        return result

    def _synthesize_sync(self, text: str) -> tuple[bytes, str]:
        import dashscope
        from dashscope.audio.tts_v2 import AudioFormat, ResultCallback, SpeechSynthesizer

        settings = self.settings
        dashscope.api_key = settings.dashscope_api_key
        dashscope.base_websocket_api_url = settings.websocket_base_url

        chunks: list[bytes] = []
        errors: list[str] = []

        class Callback(ResultCallback):
            def on_data(self, data: bytes) -> None:
                chunks.append(data)

            def on_error(self, message: str) -> None:
                errors.append(message)

        synthesizer = SpeechSynthesizer(
            model=settings.cosyvoice_model,
            voice=settings.cosyvoice_voice,
            format=AudioFormat.MP3_22050HZ_MONO_256KBPS,
            callback=Callback(),
        )
        synthesizer.streaming_call(text)
        synthesizer.streaming_complete()
        if errors:
            raise RuntimeError(errors[-1])
        return b"".join(chunks), "audio/mpeg"


def build_adapters(settings: Settings):
    if settings.demo_mode == "aliyun":
        if not settings.dashscope_api_key:
            raise RuntimeError("DEMO_MODE=aliyun 时必须配置 DASHSCOPE_API_KEY")
        return QwenVisionAdapter(settings), FunASRAdapter(settings), CosyVoiceAdapter(settings)
    return MockVisionAdapter(), MockSTTAdapter(), None
