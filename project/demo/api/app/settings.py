from functools import lru_cache
import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    demo_mode: str = "mock"
    disable_system_proxy: bool = True
    dashscope_api_key: str = ""
    dashscope_workspace_id: str = ""
    dashscope_region: str = "beijing"
    qwen_vision_model: str = "qwen3-vl-flash"
    qwen_llm_model: str = "qwen-plus"
    fun_asr_model: str = "fun-asr-realtime"
    cosyvoice_model: str = "cosyvoice-v3-flash"
    cosyvoice_voice: str = "longanyang"
    gold_cases_path: str = "../../../evaluation/cases/all_cases.yaml"
    save_uploaded_images: bool = True
    uploaded_images_path: str = "../tmp/uploads"
    uploaded_image_retention_hours: int = 24

    @property
    def gold_path(self) -> Path:
        path = Path(self.gold_cases_path)
        if path.is_absolute():
            return path
        return (Path(__file__).resolve().parent.parent / path).resolve()

    @property
    def uploaded_images_dir(self) -> Path:
        path = Path(self.uploaded_images_path)
        if path.is_absolute():
            return path
        return (Path(__file__).resolve().parent.parent / path).resolve()

    @property
    def openai_base_url(self) -> str:
        if self.dashscope_workspace_id:
            return (
                f"https://{self.dashscope_workspace_id}.cn-beijing.maas.aliyuncs.com/"
                "compatible-mode/v1"
            )
        return "https://dashscope.aliyuncs.com/compatible-mode/v1"

    @property
    def websocket_base_url(self) -> str:
        if self.dashscope_workspace_id:
            return (
                f"wss://{self.dashscope_workspace_id}.cn-beijing.maas.aliyuncs.com/"
                "api-ws/v1/inference"
            )
        return "wss://dashscope.aliyuncs.com/api-ws/v1/inference"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def configure_process_proxy(settings: Settings) -> None:
    """Prevent this API process and its SDKs from inheriting desktop proxies."""
    if not settings.disable_system_proxy:
        return
    for name in (
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "all_proxy",
    ):
        os.environ.pop(name, None)
    os.environ["NO_PROXY"] = "*"
    os.environ["no_proxy"] = "*"
