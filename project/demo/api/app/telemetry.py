import json
import logging
import time
from pathlib import Path
from typing import Any


logger = logging.getLogger("voice_tutoring")


def append_model_call(event: dict[str, Any]) -> None:
    """Append sanitized model telemetry. Never pass prompts, audio, images, or keys."""
    log_path = Path(__file__).resolve().parents[2] / "logs" / "model-calls.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"timestamp_ms": round(time.time() * 1000), **event}
    with log_path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
