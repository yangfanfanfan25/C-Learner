"""Document persistence port used by the processing service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from app.schemas.base import PaginatedData
from app.schemas.documents import DocumentDetailResponse, DocumentRecordResponse
from app.schemas.knowledge_pipeline import KnowledgePoint


@dataclass(frozen=True)
class PersistedDocumentChunk:
    id: str
    document_id: str
    title: str
    chapter: str
    section: str
    content: str
    source_pages: list[int] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


class DocumentRepository(Protocol):
    def create_processing(self, filename: str, content_type: str, file_size: int, course_name: str, academic_year: int, semester: int) -> DocumentRecordResponse:
        ...

    def create_pending(self, filename: str, content_type: str, file_size: int, course_name: str, academic_year: int, semester: int) -> DocumentRecordResponse:
        """创建等待处理（pending）的文档记录，由异步队列随后转为 processing。"""
        ...

    def get_record(self, document_id: str) -> DocumentRecordResponse | None:
        """仅查询文档记录（不含知识切片），用于后台队列读取 file_path 等字段。"""
        ...

    def list_unfinished(self) -> list[DocumentRecordResponse]:
        """返回状态为 pending / processing 的记录（用于重启后恢复处理队列）。"""
        ...

    def mark_processing(self, document_id: str) -> None:
        """把文档状态置为 processing。"""
        ...

    def persist_chunks(
        self,
        document_id: str,
        knowledge_points: list[KnowledgePoint],
    ) -> list[PersistedDocumentChunk]:
        ...

    def mark_completed(
        self,
        document_id: str,
        chapter_count: int,
        chunk_count: int,
    ) -> DocumentRecordResponse:
        ...

    def mark_failed(self, document_id: str, error_message: str) -> DocumentRecordResponse:
        ...

    def set_file_path(self, document_id: str, file_path: str) -> None:
        ...

    def rollback(self) -> None:
        ...

    def list_documents(self, page: int, page_size: int) -> PaginatedData[DocumentRecordResponse]:
        ...

    def get_document(self, document_id: str) -> DocumentDetailResponse | None:
        ...

    def delete_document(self, document_id: str) -> bool:
        ...
