# ==============================================================================
# ReviewRecord 模块 — 复习记录数据模型
# ==============================================================================
# 功能：
#   - 定义 ReviewRecord（复习记录）表结构
#   - 记录每个知识点的学习进度和复习计划
#
# 表结构：
#   1. review_records：复习记录表
#
# 关联关系：
#   knowledge_catalog (1) ──→ (N) review_records
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sqlite.engine import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


# ==============================================================================
# ReviewRecord：复习记录表
# ==============================================================================
class ReviewRecord(Base):
    """
    复习记录表

    说明：
        - 每条记录对应一个知识点的学习状态
        - mastery_level 记录掌握程度
        - next_review_at 用于安排下次复习时间（间隔重复算法）

    掌握程度：
        0 = 未学习
        1 = 了解
        2 = 理解
        3 = 掌握
        4 = 熟练
        5 = 精通
    """

    __tablename__ = "review_records"
    __table_args__ = (
        Index("idx_review_next", "next_review_at"),
        Index("idx_review_catalog", "catalog_id"),
        Index("idx_review_mastery", "mastery_level"),
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
    catalog_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("knowledge_catalog.id", ondelete="CASCADE"),
        nullable=False,
        comment="关联知识目录 ID",
    )

    # --------------------------------------------------------------------------
    # 复习统计
    # --------------------------------------------------------------------------
    review_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="累计复习次数",
    )
    last_reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="上次复习时间",
    )
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="下次复习时间",
    )

    # --------------------------------------------------------------------------
    # 掌握程度
    # --------------------------------------------------------------------------
    mastery_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="掌握程度：0=未学习, 1=了解, 2=理解, 3=掌握, 4=熟练, 5=精通",
    )
    incorrect_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="累计答错次数",
    )

    # --------------------------------------------------------------------------
    # 备注
    # --------------------------------------------------------------------------
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="学习笔记",
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
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=_utcnow,
        comment="更新时间",
    )

    def __repr__(self) -> str:
        return f"<ReviewRecord(id={self.id}, catalog_id={self.catalog_id}, mastery={self.mastery_level})>"
