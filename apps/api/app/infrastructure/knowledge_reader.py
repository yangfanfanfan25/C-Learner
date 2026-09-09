"""SQLAlchemy 知识文档读取实现。

通过 ``DocumentRepository``（port）读取文档记录与知识切片，
复用以 ``build_knowledge_markdown`` 拼装的章节化 Markdown。
"""

from __future__ import annotations

from app.domain.knowledge_markdown import build_knowledge_markdown
from app.domain.ports.documents import DocumentRepository
from app.schemas.documents import DocumentRecordResponse


class SQLAlchemyKnowledgeDocumentReader:
    """基于文档 repository 的知识读取实现（只读，无状态）。"""

    def __init__(self, repository: DocumentRepository) -> None:
        self.repository = repository

    def get_documents(self, document_ids: list[str]) -> list[DocumentRecordResponse]:
        """按 ID 取已完成处理且有知识切片的文档记录（保持入参顺序）。"""
        result: list[DocumentRecordResponse] = []
        for document_id in document_ids:
            detail = self.repository.get_document(document_id)
            if detail is None or detail.status != "completed" or not detail.chunks:
                continue
            result.append(detail)
        return result

    def read_markdown(
        self,
        document_ids: list[str],
        max_chars_per_doc: int = 20000,
    ) -> dict[str, str]:
        result: dict[str, str] = {}
        for document_id in document_ids:
            detail = self.repository.get_document(document_id)
            if detail is None or not detail.chunks:
                continue
            markdown = build_knowledge_markdown(detail)
            result[document_id] = markdown[:max_chars_per_doc]
        return result
