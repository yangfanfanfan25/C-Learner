"""长期记忆 ORM 模型（Phase 1：L0 消息 + 游标）。"""

from __future__ import annotations

import uuid

from sqlalchemy import JSON, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.sqlite.engine import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class MemoryL0Message(Base):
    """L0 原始会话消息（结构化真源 + 时间戳游标查询）。"""

    __tablename__ = "memory_l0_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(String(64), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    recorded_at_ms: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class MemoryCursor(Base):
    """键值游标表（L1 批窗口 / L2 增量读的时间戳游标）。"""

    __tablename__ = "memory_cursors"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class MemoryL1Atom(Base):
    """L1 记忆原子（结构化真源 + updated_at 游标）。"""

    __tablename__ = "memory_l1_atoms"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False)
    source_message_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    scene_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # server_default 与迁移保持一致（DB 层默认值），default 供 ORM 插入时使用
    activity: Mapped[str] = mapped_column(
        String(20), nullable=False, default="conversation", server_default=text("'conversation'")
    )
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scope: Mapped[str] = mapped_column(
        String(20), nullable=False, default="activity", server_default=text("'activity'")
    )
    # `metadata` 是 SQLAlchemy 声明式 API 的保留属性名，列名仍用 "metadata"，
    # Python 属性名改用 `metadata_`。
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    timestamps: Mapped[list | None] = mapped_column(JSON, nullable=True)
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at_ms: Mapped[int] = mapped_column(Integer, nullable=False, index=True)


class MemoryGenerationLog(Base):
    """生成日志（l0→l1→l2 血缘）。"""

    __tablename__ = "memory_generation_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid_str)
    layer: Mapped[str] = mapped_column(String(10), nullable=False)
    input_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    output_refs: Mapped[list | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at_ms: Mapped[int] = mapped_column(Integer, nullable=False)
