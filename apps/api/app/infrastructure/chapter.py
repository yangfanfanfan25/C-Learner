# ==============================================================================
# Chapter 模块 — 章节数据模型
# ==============================================================================
# 功能：
#   - 定义 Chapter（章节）表结构
#   - 支持多层级章节结构（章→节→小节）
#
# 表结构：
#   1. chapters：章节表
#
# 关联关系：
#   domains (1) ──→ (N) chapters (1) ──→ (N) chapters (自引用)
#   chapters (1) ──→ (N) knowledge_catalog
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sqlite.engine import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


# ==============================================================================
# Chapter：章节表
# ==============================================================================
class Chapter(Base):
    """
    章节表

    说明：
        - 支持多层级章节结构：章（level=1）→ 节（level=2）→ 小节（level=3）
        - 通过 parent_id 自引用实现层级关系
        - 每个章节归属一个 Domain（科目）
    """

    __tablename__ = "chapters"
    __table_args__ = (
        Index("idx_chapters_domain", "domain_id"),
        Index("idx_chapters_parent", "parent_id"),
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
    domain_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("domains.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属科目 ID",
    )
    parent_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("chapters.id", ondelete="CASCADE"),
        nullable=True,
        comment="父章节 ID（自引用，NULL 表示顶层章）",
    )

    # --------------------------------------------------------------------------
    # 基本信息
    # --------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
        comment="章节名称",
    )
    level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="层级：1=章, 2=节, 3=小节",
    )
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序序号",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="章节描述",
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
    domain: Mapped["Domain"] = relationship(
        back_populates="chapters",
        lazy="selectin",
    )
    parent: Mapped["Chapter | None"] = relationship(
        back_populates="children",
        remote_side="Chapter.id",
        lazy="selectin",
    )
    children: Mapped[list["Chapter"]] = relationship(
        back_populates="parent",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    catalog_items: Mapped[list["KnowledgeCatalog"]] = relationship(
        back_populates="chapter_ref",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Chapter(id={self.id}, name={self.name}, level={self.level})>"
