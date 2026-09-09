# ==============================================================================
# 文档与知识切片数据模型
# ==============================================================================
# 功能：
#   - 定义文档处理和知识切片持久化的表结构
#   - 文档记录（documents）与知识切片（document_chunks）一对多
#
# 表结构：
#   1. documents：已上传文档的处理记录
#   2. document_chunks：从文档规范化 Markdown 中提取的知识切片
#
# 关联关系：
#   documents (1) ──→ (N) document_chunks（级联删除）
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sqlite.engine import Base
from app.domain.ports.documents import PersistedDocumentChunk
from app.schemas.base import PaginatedData
from app.schemas.documents import (
    DocumentChunkSummary,
    DocumentDetailResponse,
    DocumentRecordResponse,
)
from app.schemas.knowledge_pipeline import KnowledgePoint


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


class DocumentRecord(Base):
    """已上传文档的处理记录。

    状态流转：
        pending → processing → completed
                           └→ failed

    chapter_count / chunk_count 为处理成功后回填的统计量。
    """

    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        comment="主键 UUID",
    )
    filename: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="原始文件名",
    )
    # server_default 与迁移保持一致（DB 层默认值），default 供 ORM 插入时使用
    course_name: Mapped[str] = mapped_column(
        String(200), nullable=False, default="未分类", server_default=text("'未分类'")
    )
    academic_year: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    semester: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    content_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="MIME 类型",
    )
    file_size: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        comment="文件大小（字节）",
    )
    file_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="原始文件存储路径（相对 files 目录，如 <document_id>/<filename>）",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="处理状态：pending/processing/completed/failed",
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="错误信息（status=failed 时记录具体 stage 与可读错误）",
    )
    chapter_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="章节数量",
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="知识切片数量",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="处理完成时间",
    )

    chunks: Mapped[list["DocumentChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DocumentRecord(id={self.id}, filename={self.filename}, status={self.status})>"


class DocumentChunk(Base):
    """从文档规范化 Markdown 中提取的知识切片。

    每个切片对应一个可独立复习的概念、事实、流程或对比项。
    source_pages / tags 以 JSON 数组存储。
    """

    __tablename__ = "document_chunks"

    # 索引名与迁移 7f3d9e21b8a4 保持一致，避免 autogenerate 误判为待删除索引
    __table_args__ = (Index("idx_document_chunks_document", "document_id"),)

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        comment="主键 UUID",
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属文档 ID",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="知识切片标题",
    )
    chapter: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="所属章节名称",
    )
    section: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="",
        comment="所属小节名称",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="知识切片内容",
    )
    source_pages: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="来源页码列表：[1, 2]",
    )
    tags: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=list,
        comment="标签列表：[\"tea\", \"history\"]",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )

    document: Mapped["DocumentRecord"] = relationship(
        back_populates="chunks",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<DocumentChunk(id={self.id}, title={self.title}, document_id={self.document_id})>"


class SQLAlchemyDocumentRepository:
    """SQLite implementation of the document persistence port."""

    def __init__(self, db) -> None:
        self.db = db

    def create_processing(self, filename: str, content_type: str, file_size: int, course_name: str = "未分类", academic_year: int = 0, semester: int = 1) -> DocumentRecordResponse:
        record = DocumentRecord(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            course_name=course_name, academic_year=academic_year, semester=semester,
            status="processing",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return DocumentRecordResponse.model_validate(record)

    def create_pending(self, filename: str, content_type: str, file_size: int, course_name: str = "未分类", academic_year: int = 0, semester: int = 1) -> DocumentRecordResponse:
        record = DocumentRecord(
            filename=filename,
            content_type=content_type,
            file_size=file_size,
            course_name=course_name, academic_year=academic_year, semester=semester,
            status="pending",
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return DocumentRecordResponse.model_validate(record)

    def get_record(self, document_id: str) -> DocumentRecordResponse | None:
        record = self.db.query(DocumentRecord).filter(DocumentRecord.id == document_id).first()
        if record is None:
            return None
        return DocumentRecordResponse.model_validate(record)

    def list_unfinished(self) -> list[DocumentRecordResponse]:
        rows = (
            self.db.query(DocumentRecord)
            .filter(DocumentRecord.status.in_(["pending", "processing"]))
            .order_by(DocumentRecord.created_at.asc())
            .all()
        )
        return [DocumentRecordResponse.model_validate(row) for row in rows]

    def mark_processing(self, document_id: str) -> None:
        record = self._require_record(document_id)
        record.status = "processing"
        self.db.commit()

    def persist_chunks(
        self,
        document_id: str,
        knowledge_points: list[KnowledgePoint],
    ) -> list[PersistedDocumentChunk]:
        rows: list[DocumentChunk] = []
        for point in knowledge_points:
            row = DocumentChunk(
                document_id=document_id,
                title=point.knowledge,
                chapter=point.chapter,
                section=point.section,
                content=point.content,
                source_pages=list(point.source_pages),
                tags=list(point.tags),
            )
            self.db.add(row)
            rows.append(row)
        self.db.flush()
        return [
            PersistedDocumentChunk(
                id=row.id,
                document_id=row.document_id,
                title=row.title,
                chapter=row.chapter,
                section=row.section,
                content=row.content,
                source_pages=list(row.source_pages or []),
                tags=list(row.tags or []),
            )
            for row in rows
        ]

    def mark_completed(
        self,
        document_id: str,
        chapter_count: int,
        chunk_count: int,
    ) -> DocumentRecordResponse:
        record = self._require_record(document_id)
        record.status = "completed"
        record.chapter_count = chapter_count
        record.chunk_count = chunk_count
        record.processed_at = _utcnow()
        self.db.commit()
        self.db.refresh(record)
        return DocumentRecordResponse.model_validate(record)

    def set_file_path(self, document_id: str, file_path: str) -> None:
        record = self._require_record(document_id)
        record.file_path = file_path
        self.db.commit()

    def mark_failed(self, document_id: str, error_message: str) -> DocumentRecordResponse:
        self.db.rollback()
        record = self._require_record(document_id)
        record.status = "failed"
        record.error_message = error_message
        record.processed_at = _utcnow()
        self.db.commit()
        self.db.refresh(record)
        return DocumentRecordResponse.model_validate(record)

    def rollback(self) -> None:
        self.db.rollback()

    def list_documents(self, page: int, page_size: int) -> PaginatedData[DocumentRecordResponse]:
        total = self.db.query(func.count(DocumentRecord.id)).scalar() or 0
        rows = (
            self.db.query(DocumentRecord)
            .order_by(DocumentRecord.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return PaginatedData(
            items=[DocumentRecordResponse.model_validate(row) for row in rows],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=(total + page_size - 1) // page_size if total else 0,
        )

    def get_document(self, document_id: str) -> DocumentDetailResponse | None:
        record = self.db.query(DocumentRecord).filter(DocumentRecord.id == document_id).first()
        if record is None:
            return None
        chunks = (
            self.db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.created_at.asc())
            .all()
        )
        return DocumentDetailResponse(
            **DocumentRecordResponse.model_validate(record).model_dump(),
            chunks=[DocumentChunkSummary.model_validate(chunk) for chunk in chunks],
        )

    def delete_document(self, document_id: str) -> bool:
        record = self.db.query(DocumentRecord).filter(DocumentRecord.id == document_id).first()
        if record is None:
            return False
        self.db.delete(record)
        self.db.commit()
        return True

    def _require_record(self, document_id: str) -> DocumentRecord:
        record = self.db.query(DocumentRecord).filter(DocumentRecord.id == document_id).first()
        if record is None:
            raise RuntimeError(f"文档记录不存在: {document_id}")
        return record
