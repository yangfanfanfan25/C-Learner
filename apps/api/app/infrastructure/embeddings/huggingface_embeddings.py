"""Local Hugging Face (sentence-transformers) embedding provider.

Uses the ``BAAI/bge-small-zh-v1.5`` model cached on this machine by default
and follows the BGE retrieval recipe (query-side instruction prefix, no prefix
on document chunks). The underlying ``langchain_huggingface.HuggingFaceEmbeddings``
is created lazily so importing this module never requires loading a model.
"""

from __future__ import annotations

from typing import Any

from app.core.config import Settings, get_settings
from app.domain.ports.embeddings import EmbeddingProvider

# BGE 官方检索指令前缀：仅在检索（query）侧使用，文档侧不加。
# 参考 https://huggingface.co/BAAI/bge-small-zh-v1.5
_BGE_QUERY_PREFIX = "为这个句子生成表示以用于检索相关文章："


class LangChainHuggingFaceEmbeddings:
    """Embedding provider backed by a local sentence-transformers model.

    The model is loaded lazily via ``langchain_huggingface.HuggingFaceEmbeddings``
    (the langchain-standard wrapper), so constructing this class does not load
    the model or require network access. The expected dimension is read from the
    loaded model and validated against settings on first use to catch config
    drift early.
    """

    def __init__(
        self,
        model_name: str,
        expected_dimension: int,
        device: str = "cpu",
    ) -> None:
        self._model_name = model_name
        self._expected_dimension = expected_dimension
        self._device = device
        self._client: Any | None = None
        self._dimension: int | None = None

    def _ensure_client(self) -> Any:
        if self._client is None:
            from langchain_huggingface import HuggingFaceEmbeddings

            self._client = HuggingFaceEmbeddings(
                model_name=self._model_name,
                model_kwargs={"device": self._device},
                encode_kwargs={"normalize_embeddings": True},
            )
            self._dimension = self._client._client.get_sentence_embedding_dimension()
        return self._client

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        client = self._ensure_client()
        self._validate_dimension()
        return client.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        client = self._ensure_client()
        self._validate_dimension()
        return client.embed_query(f"{_BGE_QUERY_PREFIX}{text}")

    def _validate_dimension(self) -> None:
        if self._dimension is not None and self._dimension != self._expected_dimension:
            raise RuntimeError(
                f"Embedding 模型 {self._model_name} 维度为 {self._dimension}，"
                f"与配置 EMBEDDING_DIMENSION={self._expected_dimension} 不一致，"
                "请同步调整配置。"
            )


def create_huggingface_embedding_provider(
    settings: Settings | None = None,
) -> LangChainHuggingFaceEmbeddings:
    """Factory that wires the local embedding provider to application settings."""
    settings = settings or get_settings()
    return LangChainHuggingFaceEmbeddings(
        model_name=settings.embedding_model_name,
        expected_dimension=settings.embedding_dimension,
    )
