"""Embedding provider infrastructure and process-level lifecycle."""

from __future__ import annotations

import asyncio
import logging
from threading import Lock

from app.core.config import Settings, get_settings

from app.infrastructure.embeddings.huggingface_embeddings import (
    LangChainHuggingFaceEmbeddings,
    create_huggingface_embedding_provider,
)
from app.infrastructure.embeddings.openai_embeddings import (
    LangChainOpenAIEmbeddings,
    create_embedding_provider,
)

logger = logging.getLogger(__name__)

_provider: LangChainHuggingFaceEmbeddings | None = None
_provider_lock = Lock()


def get_embedding_provider(settings: Settings | None = None) -> LangChainHuggingFaceEmbeddings:
    """Return the process-level embedding provider.

    The underlying sentence-transformer model is expensive to load and is safe
    to reuse for query inference. Keeping the provider here prevents every Chat
    request from constructing a new lazy-loading wrapper.
    """
    global _provider
    settings = settings or get_settings()
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = create_huggingface_embedding_provider(settings)
    return _provider


async def warmup_embedding_provider(settings: Settings | None = None) -> float:
    """Load and probe the local model during application startup.

    Returns the warmup duration in seconds. Failure is propagated so the
    application lifecycle can log it while leaving the provider available for a
    later retry on the first request.
    """
    loop = asyncio.get_running_loop()
    started = loop.time()
    provider = get_embedding_provider(settings)
    await asyncio.to_thread(provider.embed_query, "启动预热")
    duration = loop.time() - started
    logger.info("Embedding provider warmed up in %.3fs", duration)
    return duration


def reset_embedding_provider() -> None:
    """Drop the process-level provider for tests and application shutdown."""
    global _provider
    with _provider_lock:
        _provider = None

__all__ = [
    "LangChainHuggingFaceEmbeddings",
    "LangChainOpenAIEmbeddings",
    "create_embedding_provider",
    "create_huggingface_embedding_provider",
    "get_embedding_provider",
    "warmup_embedding_provider",
    "reset_embedding_provider",
]
