"""Semantic vector store port (domain contract).

Defines the consumer-driven protocol for indexing knowledge chunks, searching
them by query vector, and deleting them by document. Infrastructure
implementations (Milvus Lite) live under ``app.infrastructure.milvus``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class SemanticChunk:
    """A chunk of knowledge that can be indexed into the vector store."""

    chunk_id: str
    document_id: str
    title: str
    chapter: str
    section: str
    content: str
    vector: list[float] = field(default_factory=list)
    source_pages: list[int] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticHit:
    """A single retrieval result with similarity score."""

    chunk_id: str
    document_id: str
    title: str
    chapter: str
    section: str
    content: str
    score: float


class SemanticVectorStore(Protocol):
    """Index, search and delete knowledge chunks by vector."""

    async def index_chunks(self, chunks: list[SemanticChunk]) -> int:
        """Index chunks and return the number of inserted rows."""
        ...

    async def search(self, query_vector: list[float], top_k: int) -> list[SemanticHit]:
        """Return the top-k nearest chunks ordered by descending similarity."""
        ...

    async def delete_by_document(self, document_id: str) -> None:
        """Delete every chunk belonging to *document_id*."""
        ...
