# ==============================================================================
# Exam 模块 — 考试题目数据模型
# ==============================================================================
# 功能：
#   - 定义 ExamRecord（考试题目）表结构
#   - 记录 LLM 生成的题目及其关联的知识点
#
# 表结构：
#   1. exam_records：考试题目表
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sqlite.engine import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


# ==============================================================================
# ExamRecord：考试题目表
# ==============================================================================
class ExamRecord(Base):
    """
    考试题目表

    说明：
        - 记录 LLM 生成的每一道题目
        - knowledge_combo 存储关联的知识点 ID 列表（JSON 数组字符串）
        - difficulty 标记题目难度层级
        - is_used 标记该题是否已被使用

    难度层级：
        1 = 概念层（单知识点考查）
        2 = 关联层（多知识点关联）
        3 = 深层关联（跨领域综合）
    """

    __tablename__ = "exam_records"
    __table_args__ = (
        Index("idx_exam_combo", "knowledge_combo"),
        Index("idx_exam_domain", "domain"),
        Index("idx_exam_difficulty", "difficulty"),
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
    # 题目信息
    # --------------------------------------------------------------------------
    knowledge_combo: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="关联知识点 ID 列表（JSON 数组字符串）",
    )
    difficulty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="难度层级：1=概念层, 2=关联层, 3=深层关联",
    )
    question_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="题目类型：choice/fill/solve",
    )
    question_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="题目内容",
    )
    answer_text: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="参考答案",
    )

    # --------------------------------------------------------------------------
    # 分类信息
    # --------------------------------------------------------------------------
    domain: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="所属领域/科目",
    )

    # --------------------------------------------------------------------------
    # 状态
    # --------------------------------------------------------------------------
    is_used: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="是否已被使用",
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

    def __repr__(self) -> str:
        return f"<ExamRecord(id={self.id}, difficulty={self.difficulty}, domain={self.domain})>"
