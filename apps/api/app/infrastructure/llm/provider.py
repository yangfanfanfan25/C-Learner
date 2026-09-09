"""LangChain chat model provider."""

from __future__ import annotations

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from app.core.config import Settings, get_settings


def create_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Create the configured chat model through LangChain's standard factory."""
    settings = settings or get_settings()
    if not settings.llm_api_key:
        raise RuntimeError("LLM_API_KEY 未配置，无法初始化智能问答模型")

    return init_chat_model(
        settings.llm_model_name,
        model_provider=settings.llm_model_provider,
        api_key=settings.llm_api_key,
        base_url=settings.llm_api_base_url,
        temperature=0.7,
        streaming=True,
    )
