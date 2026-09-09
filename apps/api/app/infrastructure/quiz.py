# ==============================================================================
# Quiz 模块 — 模拟练习试卷数据模型
# ==============================================================================
# 功能：
#   - 定义 QuizPaper（试卷）表结构
#   - 记录 LLM 生成的整套试卷及其关联文档、需求与导出文件路径
#
# 表结构：
#   1. quiz_papers：试卷表
#
# 说明：
#   - questions_json 保存完整试卷 JSON（题目+答案+解析，已通过 QuizPaper schema 校验）
#   - file_path_md / file_path_json 为相对 files 根目录的导出文件路径
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sqlite.engine import Base


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


def _uuid_str() -> str:
    """生成 UUID 字符串。"""
    return str(uuid.uuid4())


class QuizPaper(Base):
    """模拟练习试卷表。

    说明：
        - 每次生成一套试卷创建一条记录
        - session_id 记录来源会话（可空，保留扩展空间）
        - document_ids / document_titles 记录出题依据的文档
        - questions_json 为已校验的完整试卷 JSON
    """

    __tablename__ = "quiz_papers"

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
    # 试卷信息
    # --------------------------------------------------------------------------
    session_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        comment="来源会话 ID（可空）",
    )
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="试卷标题",
    )
    document_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="出题依据的文档 ID 列表",
    )
    document_titles: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="文档文件名列表（冗余存储，避免反查）",
    )
    requirements: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="用户出题需求原文",
    )
    question_types: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        comment="实际题型列表",
    )
    difficulty: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="难度等级：1=基础, 2=进阶, 3=综合",
    )
    questions_json: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="完整试卷 JSON（题目+答案+解析，已校验）",
    )

    # --------------------------------------------------------------------------
    # 导出文件
    # --------------------------------------------------------------------------
    file_path_md: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Markdown 导出文件相对路径（quiz_papers/<id>/<title>.md）",
    )
    file_path_json: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="JSON 导出文件相对路径（quiz_papers/<id>/<title>.json）",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )

    def __repr__(self) -> str:
        return f"<QuizPaper(id={self.id}, title={self.title}, difficulty={self.difficulty})>"
