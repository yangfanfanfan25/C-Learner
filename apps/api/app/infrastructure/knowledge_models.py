# ==============================================================================
# Knowledge 模块 — 知识体系数据模型
# ==============================================================================
# 功能：
#   - 定义知识体系所有数据库表结构
#   - 表之间的关联关系
#
# 表结构：
#   1. knowledge_catalog：知识目录表
#   2. knowledge_content：知识内容表（Markdown 正文）
#   3. knowledge_links：知识点关联表（双向关系）
#   4. knowledge_source：知识来源表（原始文档追溯）
#
# 关联关系：
#   chapters (1) ──→ (N) knowledge_catalog (1) ──→ (1) knowledge_content
#   knowledge_catalog (1) ──→ (N) knowledge_source
#   knowledge_catalog (N) ──→ (N) knowledge_catalog（通过 knowledge_links）
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sqlite.engine import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


# ==============================================================================
# KnowledgeCatalog：知识目录表
# ==============================================================================
class KnowledgeCatalog(Base):
    """
    知识目录表

    说明：
        - 每个目录项对应一个知识点的索引
        - 隶属于某个章节（chapter_id）
        - domain/chapter/section 为冗余字段，用于快速检索
        - 通过 content 关联详细内容，通过 sources 关联原始文档
    """

    __tablename__ = "knowledge_catalog"
    __table_args__ = (
        Index("idx_catalog_chapter", "chapter_id"),
        Index("idx_catalog_domain", "domain"),
    )

    # --------------------------------------------------------------------------
    # 主键
    # --------------------------------------------------------------------------
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        comment="主键 UUID",
    )

    # --------------------------------------------------------------------------
    # 外键
    # --------------------------------------------------------------------------
    chapter_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属章节 ID",
    )

    # --------------------------------------------------------------------------
    # 基本信息
    # --------------------------------------------------------------------------
    title: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="知识点标题",
    )

    # --------------------------------------------------------------------------
    # 冗余字段（用于快速检索和展示）
    # --------------------------------------------------------------------------
    domain: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="所属领域/科目（冗余字段）",
    )
    chapter: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="所属章节名称（冗余字段）",
    )
    section: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="所属小节名称（冗余字段）",
    )

    # --------------------------------------------------------------------------
    # 排序
    # --------------------------------------------------------------------------
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序序号",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="创建时间",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    chapter_ref: Mapped["Chapter"] = relationship(
        back_populates="catalog_items",
        lazy="selectin",
    )
    content: Mapped["KnowledgeContent | None"] = relationship(
        back_populates="catalog",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
    sources: Mapped[list["KnowledgeSource"]] = relationship(
        back_populates="catalog",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    outgoing_links: Mapped[list["KnowledgeLink"]] = relationship(
        back_populates="source_catalog",
        foreign_keys="KnowledgeLink.source_id",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    incoming_links: Mapped[list["KnowledgeLink"]] = relationship(
        back_populates="target_catalog",
        foreign_keys="KnowledgeLink.target_id",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeCatalog(id={self.id}, title={self.title}, domain={self.domain})>"


# ==============================================================================
# KnowledgeContent：知识内容表
# ==============================================================================
class KnowledgeContent(Base):
    """
    知识内容表

    说明：
        - 与 KnowledgeCatalog 一对一关联
        - 存储知识点的 Markdown 正文内容
        - key_points / formulas / examples 均为 JSON 数组字符串
        - difficulty_level 和 exam_frequency 用于辅助出题和复习优先级
    """

    __tablename__ = "knowledge_content"
    __table_args__ = (
        Index("idx_content_catalog", "catalog_id"),
    )

    # --------------------------------------------------------------------------
    # 主键
    # --------------------------------------------------------------------------
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        comment="主键 UUID",
    )

    # --------------------------------------------------------------------------
    # 外键（一对一）
    # --------------------------------------------------------------------------
    catalog_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_catalog.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        comment="关联知识目录 ID（唯一）",
    )

    # --------------------------------------------------------------------------
    # 内容
    # --------------------------------------------------------------------------
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Markdown 格式正文内容",
    )
    key_points: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="要点列表（JSON 数组字符串）",
    )
    formulas: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="公式列表（JSON 数组字符串，LaTeX 格式）",
    )
    examples: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="示例列表（JSON 数组字符串）",
    )

    # --------------------------------------------------------------------------
    # 难度与频率
    # --------------------------------------------------------------------------
    difficulty_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="难度等级：1=基础, 2=中等, 3=进阶",
    )
    exam_frequency: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="考试出现频率（用于出题权重）",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="创建时间",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    catalog: Mapped["KnowledgeCatalog"] = relationship(
        back_populates="content",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeContent(id={self.id}, catalog_id={self.catalog_id})>"


# ==============================================================================
# KnowledgeLink：知识点关联表
# ==============================================================================
class KnowledgeLink(Base):
    """
    知识点关联表

    说明：
        - 记录两个知识点之间的关系
        - relation_type 定义关系类型
        - weight 表示关联强度（0.0~1.0）
        - is_cross_domain 标记是否跨领域关联

    关系类型：
        - prerequisite：前置知识
        - composable：可组合
        - similar_to：相似
        - part_of：属于
        - leads_to：引出
        - easily_confused：易混淆
    """

    __tablename__ = "knowledge_links"
    __table_args__ = (
        UniqueConstraint("source_id", "target_id", name="uq_link_source_target"),
        Index("idx_links_source", "source_id"),
        Index("idx_links_target", "target_id"),
    )

    # --------------------------------------------------------------------------
    # 主键
    # --------------------------------------------------------------------------
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        comment="主键 UUID",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    source_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_catalog.id", ondelete="CASCADE"),
        nullable=False,
        comment="源知识点 ID",
    )
    target_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_catalog.id", ondelete="CASCADE"),
        nullable=False,
        comment="目标知识点 ID",
    )

    # --------------------------------------------------------------------------
    # 关系属性
    # --------------------------------------------------------------------------
    relation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="关系类型：prerequisite/composable/similar_to/part_of/leads_to/easily_confused",
    )
    weight: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=1.0,
        comment="关联强度（0.0~1.0）",
    )
    context: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="关联上下文说明",
    )
    is_cross_domain: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否跨领域关联",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="创建时间",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    source_catalog: Mapped["KnowledgeCatalog"] = relationship(
        back_populates="outgoing_links",
        foreign_keys=[source_id],
        lazy="selectin",
    )
    target_catalog: Mapped["KnowledgeCatalog"] = relationship(
        back_populates="incoming_links",
        foreign_keys=[target_id],
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeLink(source={self.source_id}, target={self.target_id}, type={self.relation_type})>"


# ==============================================================================
# KnowledgeSource：知识来源表
# ==============================================================================
class KnowledgeSource(Base):
    """
    知识来源表

    说明：
        - 记录知识点的原始文档来源
        - catalog_id 可为 NULL（尚未关联到知识点的待处理文档）
        - source_type 记录原始文件类型
        - markdown_content 存储从原始文件中提取的文本
    """

    __tablename__ = "knowledge_source"
    __table_args__ = (
        Index("idx_source_catalog", "catalog_id"),
    )

    # --------------------------------------------------------------------------
    # 主键
    # --------------------------------------------------------------------------
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=_uuid_str,
        comment="主键 UUID",
    )

    # --------------------------------------------------------------------------
    # 外键
    # --------------------------------------------------------------------------
    catalog_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("knowledge_catalog.id", ondelete="SET NULL"),
        nullable=True,
        comment="关联知识目录 ID（NULL 表示尚未关联）",
    )

    # --------------------------------------------------------------------------
    # 来源信息
    # --------------------------------------------------------------------------
    source_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="来源文件类型：pdf/ppt/docx/image",
    )
    source_filename: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="原始文件名",
    )
    source_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="文件存储路径",
    )
    markdown_content: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="从原始文件提取的 Markdown 内容",
    )
    page_range: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="页码范围（如 1-5, 10）",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    extracted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="内容提取时间",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        comment="创建时间",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    catalog: Mapped["KnowledgeCatalog | None"] = relationship(
        back_populates="sources",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<KnowledgeSource(id={self.id}, type={self.source_type}, filename={self.source_filename})>"
