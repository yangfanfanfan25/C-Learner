"""Persist first-run configuration in an env file and verify the LLM connection."""

from __future__ import annotations

from pathlib import Path
import os
import tempfile

from langchain_core.messages import HumanMessage

from app.core.config import Settings, get_settings
from app.infrastructure.llm.provider import create_chat_model
from app.schemas.setup import ModelOption, SetupConfigRequest, SetupStatus


MODEL_OPTIONS = [
    ModelOption(id="deepseek-chat", label="DeepSeek Chat", base_url="https://api.deepseek.com/v1"),
    ModelOption(id="deepseek-reasoner", label="DeepSeek Reasoner", base_url="https://api.deepseek.com/v1"),
]


def env_path() -> Path:
    return Path(__file__).resolve().parents[2] / ".env"


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def write_env_config(request: SetupConfigRequest) -> None:
    path = env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    values = {
        "LLM_API_KEY": request.api_key,
        "LLM_MODEL_NAME": request.model_name,
        "LLM_API_BASE_URL": request.base_url.rstrip("/"),
        "LLM_MODEL_PROVIDER": request.provider,
    }
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = existing.splitlines()
    seen: set[str] = set()
    output: list[str] = []
    for line in lines:
        key = line.split("=", 1)[0].strip() if "=" in line else ""
        if key in values:
            output.append(f'{key}="{_escape(values[key])}"')
            seen.add(key)
        else:
            output.append(line)
    for key, value in values.items():
        if key not in seen:
            output.append(f'{key}="{_escape(value)}"')
    fd, temp_name = tempfile.mkstemp(prefix=".env.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write("\n".join(output).rstrip() + "\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    get_settings.cache_clear()


def _friendly_error(exc: Exception) -> str:
    text = str(exc).lower()
    if "401" in text or "unauthorized" in text or "api key" in text or "authentication" in text:
        return "API Key 无效或已过期，请检查后重试。"
    if "timeout" in text or "timed out" in text:
        return "连接模型超时，请检查网络或稍后重试。"
    if "404" in text or "not found" in text or "model" in text and "not" in text:
        return "模型或接口地址不可用，请检查模型名称和 Base URL。"
    if "connection" in text or "dns" in text or "connect" in text:
        return "暂时无法连接模型服务，请检查网络和 Base URL。"
    return "模型连接失败，请检查配置后重试。"


async def check_connection(settings: Settings | None = None) -> tuple[bool, str]:
    current = settings or get_settings()
    if not current.llm_api_key:
        return False, "请先填写 API Key。"
    try:
        model = create_chat_model(current)
        await model.ainvoke([HumanMessage(content="Reply with OK only.")])
        return True, "模型连接成功。"
    except Exception as exc:  # provider-specific exception types vary
        return False, _friendly_error(exc)


def current_status(connected: bool = False, message: str | None = None) -> SetupStatus:
    settings = get_settings()
    configured = bool(settings.llm_api_key)
    return SetupStatus(
        configured=configured,
        connected=connected,
        model_name=settings.llm_model_name,
        base_url=settings.llm_api_base_url,
        api_key_configured=configured,
        message=message or ("已配置，尚未检测连接。" if configured else "尚未配置模型。"),
    )


def friendly_error_message(exc: Exception) -> str:
    return _friendly_error(exc)
