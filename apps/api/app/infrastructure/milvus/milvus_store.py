"""Milvus Lite vector store built on pymilvus.MilvusClient.

The client uses the local database URI mode: ``MilvusClient(uri=<path>.db)``
spins up an embedded Milvus Lite instance backed by a local file. The
``pymilvus`` dependency is imported lazily so the application can start even
when Milvus is not installed or not yet initialised.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.core.config import Settings, get_settings
from app.domain.ports.semantic_store import SemanticChunk, SemanticHit, SemanticVectorStore

logger = logging.getLogger(__name__)

_VARCHAR_MAX = 65535
# Milvus Lite uses an embedded gRPC server.  Avoid PyMilvus' aggressive
# 10-second idle pings, which the local server may rate-limit as too_many_pings.
_GRPC_OPTIONS = {
    "grpc.keepalive_time_ms": 300_000,
    "grpc.keepalive_timeout_ms": 20_000,
    "grpc.keepalive_permit_without_calls": False,
}
_vector_store: MilvusLiteVectorStore | None = None


class MilvusLiteVectorStore:
    """Index and search knowledge chunks in a local Milvus Lite database."""

    def __init__(
        self,
        uri: Path,
        collection_name: str,
        dimension: int,
    ) -> None:
        self._uri = str(uri)
        self._collection_name = collection_name
        self._dimension = dimension
        self._client: Any | None = None

    # -- lifecycle -----------------------------------------------------------

    def _ensure_client(self) -> Any:
        if self._client is None:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self._uri, grpc_options=_GRPC_OPTIONS)
            self._ensure_collection()
        return self._client

    def _ensure_collection(self) -> None:
        if not self._client.has_collection(self._collection_name):
            from pymilvus import DataType

            schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
            schema.add_field(field_name="chunk_id", datatype=DataType.VARCHAR, is_primary=True, max_length=64)
            schema.add_field(field_name="document_id", datatype=DataType.VARCHAR, max_length=64)
            schema.add_field(field_name="title", datatype=DataType.VARCHAR, max_length=512)
            schema.add_field(field_name="chapter", datatype=DataType.VARCHAR, max_length=512)
            schema.add_field(field_name="section", datatype=DataType.VARCHAR, max_length=512)
            schema.add_field(field_name="content", datatype=DataType.VARCHAR, max_length=_VARCHAR_MAX)
            schema.add_field(field_name="source_pages", datatype=DataType.JSON)
            schema.add_field(field_name="tags", datatype=DataType.JSON)
            schema.add_field(field_name="vector", datatype=DataType.FLOAT_VECTOR, dim=self._dimension)

            index_params = self._client.prepare_index_params()
            index_params.add_index(field_name="vector", index_type="AUTOINDEX", metric_type="COSINE")
            self._client.create_collection(
                self._collection_name,
                schema=schema,
                index_params=index_params,
            )

        # Milvus 要求 collection 在 search/query 前处于 loaded 状态。持久化的
        # DB 在进程重启后 collection 默认处于 released，必须显式 load。
        # load 是幂等操作：重复调用已加载的 collection 不会报错。
        self._client.load_collection(self._collection_name)

    def close(self) -> None:
        """Release the underlying Milvus client."""
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # pragma: no cover - defensive close
                logger.warning("Milvus client close failed: %s", exc)
            self._client = None

    # -- protocol ------------------------------------------------------------

    async def index_chunks(self, chunks: list[SemanticChunk]) -> int:
        client = self._ensure_client()
        rows = [
            {
                "chunk_id": chunk.chunk_id,
                "document_id": chunk.document_id,
                "title": chunk.title,
                "chapter": chunk.chapter,
                "section": chunk.section,
                "content": chunk.content,
                "source_pages": chunk.source_pages,
                "tags": chunk.tags,
                "vector": chunk.vector,
            }
            for chunk in chunks
        ]
        if not rows:
            return 0
        result = client.insert(self._collection_name, data=rows)
        return int(result.get("insert_count", len(rows)))

    async def search(self, query_vector: list[float], top_k: int) -> list[SemanticHit]:
        client = self._ensure_client()
        results = client.search(
            collection_name=self._collection_name,
            data=[query_vector],
            limit=top_k,
            output_fields=["chunk_id", "document_id", "title", "chapter", "section", "content"],
            search_params={"metric_type": "COSINE"},
        )
        hits: list[SemanticHit] = []
        for row in (results[0] if results else []):
            entity = row.get("entity", {})
            hits.append(
                SemanticHit(
                    chunk_id=str(entity.get("chunk_id", "")),
                    document_id=str(entity.get("document_id", "")),
                    title=str(entity.get("title", "")),
                    chapter=str(entity.get("chapter", "")),
                    section=str(entity.get("section", "")),
                    content=str(entity.get("content", "")),
                    score=float(row.get("distance", 0.0)),
                )
            )
        return hits

    async def delete_by_document(self, document_id: str) -> None:
        client = self._ensure_client()
        client.delete(
            self._collection_name,
            filter=f'document_id == "{document_id}"',
        )


def get_milvus_vector_store(settings: Settings | None = None) -> MilvusLiteVectorStore:
    """Return the process-level Milvus Lite store."""
    global _vector_store
    if _vector_store is not None:
        return _vector_store
    settings = settings or get_settings()
    settings.milvus_lite_path.parent.mkdir(parents=True, exist_ok=True)
    _vector_store = MilvusLiteVectorStore(
        uri=settings.milvus_lite_path,
        collection_name=settings.milvus_collection_name,
        dimension=settings.embedding_dimension,
    )
    return _vector_store


def close_milvus_vector_store() -> None:
    """Close and reset the process-level Milvus Lite store."""
    global _vector_store
    if _vector_store is not None:
        _vector_store.close()
    _vector_store = None
