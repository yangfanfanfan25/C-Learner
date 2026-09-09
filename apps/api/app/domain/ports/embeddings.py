"""Embedding provider port (domain contract).

Defines the minimal protocol for converting documents and queries into
dense vectors. Infrastructure implementations (OpenAI-compatible embedding
APIs) live under ``app.infrastructure.embeddings``.
"""

from __future__ import annotations

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Embed document chunks and search queries into vectors."""

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text (stable order)."""
        ...

    def embed_query(self, text: str) -> list[float]:
        """Return a single vector for a user query."""
        ...
