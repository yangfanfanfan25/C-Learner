# ==============================================================================
# Domain 模块 — 领域/科目数据模型
# ==============================================================================
# 功能：
#   - 定义 Domain（领域/科目）表结构
#   - 支持按年级、学期分类管理科目
#
# 表结构：
#   1. domains：科目表
#
# 关联关系：
#   domains (1) ──→ (N) chapters
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.sqlite.engine import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


# ==============================================================================
# Domain：领域/科目表
# ==============================================================================
class Domain(Base):
    """
    领域/科目表

    说明：
        - 每个科目对应一门课程
        - 支持按年级（大一~大四）和学期（上/下）分类
        - 通过 chapters 关联该科目下的所有章节
    """

    __tablename__ = "domains"
    __table_args__ = (
        Index("idx_domains_grade", "grade"),
        Index("idx_domains_semester", "semester"),
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
    # 基本信息
    # --------------------------------------------------------------------------
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="科目名称",
    )
    code: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="课程代码（如 MATH101）",
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="科目描述",
    )

    # --------------------------------------------------------------------------
    # 分类信息
    # --------------------------------------------------------------------------
    grade: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="适用年级：大一/大二/大三/大四",
    )
    semester: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        comment="适用学期：上/下",
    )

    # --------------------------------------------------------------------------
    # 状态与排序
    # --------------------------------------------------------------------------
    sort_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="排序序号",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="是否启用",
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
    chapters: Mapped[list["Chapter"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Domain(id={self.id}, name={self.name}, grade={self.grade})>"
