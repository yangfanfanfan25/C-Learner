"""Document processing application service.

Coordinates the knowledge pipeline (document -> structure -> Markdown ->
knowledge chunks), SQLite persistence of document/chunks, and Milvus vector
indexing. All external dependencies (pipeline, embedding provider, vector
store) are injected through the constructor so tests can supply fakes.
"""

from __future__ import annotations

import asyncio
import logging

from app.domain.ports.documents import DocumentRepository, PersistedDocumentChunk
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.file_storage import DocumentFileStorage
from app.domain.ports.knowledge_pipeline import KnowledgePipeline
from app.domain.ports.semantic_store import SemanticChunk, SemanticVectorStore
from app.schemas.base import PaginatedData
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentRecordResponse,
)

logger = logging.getLogger(__name__)

_MAX_ERROR_MESSAGE_LENGTH = 500


class DocumentProcessingService:
    """Run the document pipeline and persist document + knowledge chunks."""

    def __init__(
        self,
        repository: DocumentRepository,
        pipeline: KnowledgePipeline | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        vector_store: SemanticVectorStore | None = None,
        file_storage: DocumentFileStorage | None = None,
    ) -> None:
        self.repository = repository
        self.pipeline = pipeline
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.file_storage = file_storage

    # -- processing ----------------------------------------------------------

    async def process_document(
        self,
        filename: str,
        content_type: str,
        file_bytes: bytes,
        course_name: str = "未分类",
        academic_year: int = 0,
        semester: int = 1,
    ) -> DocumentRecordResponse:
        """Run the pipeline, persist chunks and index vectors.

        Returns the document record (status ``completed`` or ``failed``).
        Errors are captured in ``error_message`` with a readable stage message.
        """
        record = self.repository.create_processing(filename, content_type, len(file_bytes), course_name, academic_year, semester)

        try:
            if (
                self.pipeline is None
                or self.embedding_provider is None
                or self.vector_store is None
                or self.file_storage is None
            ):
                raise RuntimeError("文档处理依赖未配置")

            # 保存原始文件副本并记录路径（处理失败时文件保留）
            stored_path = self.file_storage.save(record.id, filename, file_bytes)
            self.repository.set_file_path(record.id, stored_path)

            result = await self.pipeline.run(
                document_id=record.id,
                filename=filename,
                file_bytes=file_bytes,
            )
            chunks = self.repository.persist_chunks(record.id, result.knowledge_points)
            indexed_count = await self._index_chunks(record, chunks)
            if indexed_count != len(chunks):
                raise RuntimeError(
                    f"向量索引数量不一致：expected={len(chunks)}, actual={indexed_count}"
                )

            logger.info("Document processed: %s (%d chunks)", filename, len(chunks))
            return self.repository.mark_completed(record.id, len(result.chapters), len(chunks))
        except Exception as exc:
            self.repository.rollback()
            if self.vector_store is not None:
                try:
                    await self.vector_store.delete_by_document(record.id)
                except Exception as cleanup_exc:
                    logger.error(
                        "Failed to clean vectors after document processing error: %s: %s",
                        type(cleanup_exc).__name__,
                        cleanup_exc,
                    )
            logger.exception("Document processing failed: %s", filename)
            return self.repository.mark_failed(record.id, self._readable_error(exc))

    async def _index_chunks(
        self,
        record: DocumentRecordResponse,
        chunks: list[PersistedDocumentChunk],
    ) -> int:
        if not chunks:
            return 0
        if self.embedding_provider is None or self.vector_store is None:
            raise RuntimeError("向量索引依赖未配置")
        texts = [
            f"{chunk.title}\n{chunk.content}" if chunk.title else chunk.content
            for chunk in chunks
        ]
        vectors = await asyncio.to_thread(
            self.embedding_provider.embed_documents,
            texts,
        )
        semantic_chunks = [
            SemanticChunk(
                chunk_id=chunk.id,
                document_id=record.id,
                title=chunk.title,
                chapter=chunk.chapter,
                section=chunk.section,
                content=chunk.content,
                vector=vectors[index],
                source_pages=list(chunk.source_pages or []),
                tags=list(chunk.tags or []),
            )
            for index, chunk in enumerate(chunks)
        ]
        return await self.vector_store.index_chunks(semantic_chunks)

    @staticmethod
    def _readable_error(exc: Exception) -> str:
        message = str(exc) or type(exc).__name__
        message = " ".join(message.split())
        return f"{type(exc).__name__}: {message}"[:_MAX_ERROR_MESSAGE_LENGTH]

    # -- queries -------------------------------------------------------------

    def list_documents(self, page: int, page_size: int) -> PaginatedData[DocumentRecordResponse]:
        return self.repository.list_documents(page, page_size)

    def get_document(self, document_id: str) -> DocumentDetailResponse | None:
        return self.repository.get_document(document_id)

    async def delete_document(self, document_id: str) -> bool:
        """Delete the document record, its chunks, the Milvus vectors and the stored raw file."""
        if self.repository.get_document(document_id) is None:
            return False
        if self.vector_store is None or self.file_storage is None:
            raise RuntimeError("删除文档依赖未配置")
        try:
            await self.vector_store.delete_by_document(document_id)
        except Exception as exc:
            # Vector deletion failure must not silently mask a failed delete.
            logger.error("Vector deletion failed for %s: %s", document_id, exc)
            raise
        self.file_storage.delete(document_id)
        return self.repository.delete_document(document_id)
