"""L0 memory capture orchestration."""

from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone

from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.memory import MemoryCapturePort, MemoryVectorWriter
from app.infrastructure.memory.journal import JsonlJournalStore
from app.infrastructure.memory.sanitize import sanitize_text, should_capture_l0, strip_code_blocks
from app.infrastructure.memory.sqlite_repository import SqliteMemoryRepository
from app.infrastructure.memory.vector import MilvusMemoryVectorStore
from app.schemas.memory import L0Context, L0Message

logger = logging.getLogger(__name__)


class MemoryCaptureService(MemoryCapturePort):
    """Clean and persist L0 messages using injected storage capabilities."""

    def __init__(self, sqlite_repo: SqliteMemoryRepository, journal: JsonlJournalStore,
                 vector_store: MemoryVectorWriter | None = None,
                 embedding: EmbeddingProvider | None = None, *,
                 user_id: str = "local", agent_id: str = "rag-assistant",
                 journal_category: str = "conversations") -> None:
        self._sqlite = sqlite_repo
        self._journal = journal
        self._vector_store = vector_store
        self._embedding = embedding
        self._user_id = user_id
        self._agent_id = agent_id
        self._journal_category = journal_category

    def capture_message(
        self,
        session_id: str,
        role: str,
        content: str,
        context: L0Context | None = None,
    ) -> None:
        if not should_capture_l0(content):
            return
        if role == "assistant":
            content = strip_code_blocks(content)
        msg = L0Message(id=str(uuid.uuid4()), session_id=session_id,
                        user_id=self._user_id, agent_id=self._agent_id,
                        role=role, content=sanitize_text(content),
                        context=context or L0Context(),
                        recorded_at_ms=int(time.time() * 1000))  # type: ignore[arg-type]
        self._sqlite.append(msg)
        day = datetime.fromtimestamp(msg.recorded_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        self._journal.append(self._journal_category, msg.model_dump(), day=day)
        if self._vector_store is None or self._embedding is None:
            return
        try:
            vector = self._embedding.embed_query(msg.content)
            self._vector_store.insert([{"id": msg.id, "session_id": msg.session_id,
                                        "content": msg.content,
                                        "recorded_at_ms": msg.recorded_at_ms,
                                        "vector": vector}])
        except Exception as exc:  # noqa: BLE001 - optional vector degradation
            logger.warning("L0 vector write failed (optional degradation): %s", exc)


def l1_collection_fields(dim: int) -> list:
    """Define the L1 memory collection schema."""
    from app.infrastructure.memory.vector import MilvusFieldSpec, MilvusFieldType

    return [
        MilvusFieldSpec("id", MilvusFieldType.VARCHAR, is_primary=True, max_length=64),
        MilvusFieldSpec("session_id", MilvusFieldType.VARCHAR, max_length=64),
        MilvusFieldSpec("content", MilvusFieldType.VARCHAR, max_length=65535),
        MilvusFieldSpec("vector", MilvusFieldType.FLOAT_VECTOR, dim=dim),
    ]


_l1_vector_store: MilvusMemoryVectorStore | None = None


def get_l1_memory_vector_store(settings) -> MilvusMemoryVectorStore:
    """Create or reuse the process-level L1 memory vector store singleton."""
    global _l1_vector_store
    if _l1_vector_store is None:
        settings.milvus_lite_path.parent.mkdir(parents=True, exist_ok=True)
        _l1_vector_store = MilvusMemoryVectorStore(
            uri=settings.milvus_lite_path,
            collection_name=settings.memory_milvus_l1_collection_name,
            fields=l1_collection_fields(settings.embedding_dimension),
        )
    return _l1_vector_store


def close_l1_memory_vector_store() -> None:
    """Close and drop the process-level L1 memory vector store singleton."""
    global _l1_vector_store
    if _l1_vector_store is not None:
        _l1_vector_store.close()
    _l1_vector_store = None
