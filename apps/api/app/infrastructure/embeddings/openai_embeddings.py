"""OpenAI-compatible embedding provider built on langchain-openai."""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.domain.ports.embeddings import EmbeddingProvider
from app.infrastructure.embeddings.huggingface_embeddings import (
    LangChainHuggingFaceEmbeddings,
)


class LangChainOpenAIEmbeddings:
    """Embedding provider backed by an OpenAI-compatible embeddings endpoint.

    The underlying ``langchain_openai.OpenAIEmbeddings`` client is created
    lazily so importing this module does not require network access or a
    configured key. The API key and base URL fall back to the LLM settings so
    a single local gateway can serve both chat and embeddings.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        dimension: int,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._dimension = dimension
        self._client: Any | None = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from langchain_openai import OpenAIEmbeddings

            self._client = OpenAIEmbeddings(
                model=self._model,
                api_key=self._api_key,
                base_url=self._base_url,
                dimensions=self._dimension,
            )
        return self._client

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        client = self._ensure_client()
        return client.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        client = self._ensure_client()
        return client.embed_query(text)


def create_embedding_provider(settings: Settings | None = None) -> LangChainHuggingFaceEmbeddings:
    """Factory that wires the embedding provider to application settings.

    Currently hardcoded to the local sentence-transformers model
    (``BAAI/bge-small-zh-v1.5`` by default). The OpenAI-compatible provider
    (``LangChainOpenAIEmbeddings``) is kept for future online-model support
    and can be selected here without touching callers.
    """
    from app.infrastructure.embeddings.huggingface_embeddings import (
        create_huggingface_embedding_provider,
    )

    return create_huggingface_embedding_provider(settings)
