# ==============================================================================
# 对话系统数据模型
# ==============================================================================
# 功能：
#   - 定义对话系统所有数据库表结构
#   - 表之间的关联关系
#
# 表结构：
#   1. chat_sessions：对话会话表
#   2. chat_messages：对话消息表
#
# 关联关系：
#   chat_sessions (1) ──→ (N) chat_messages
# ==============================================================================

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    ForeignKey,
    String,
    Text,
    JSON,
    func,
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
# ChatSession：对话会话表
# ==============================================================================
class ChatSession(Base):
    """
    对话会话表

    说明：
        - 每次新建对话创建一条记录
        - status 字段记录会话状态
        - title 可由首条消息自动生成或用户自定义

    状态流转：
        active → archived
    """

    __tablename__ = "chat_sessions"

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
    # 会话信息
    # --------------------------------------------------------------------------
    title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        default="新对话",
        comment="会话标题",
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="active",
        comment="会话状态：active/archived",
    )
    capabilities: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="会话默认聊天能力列表：knowledge/practice/web_search；最近一次消息用到的能力自动同步",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="创建时间",
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="最后活跃时间",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    messages: Mapped[list["ChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="ChatMessage.created_at",
    )

    def __repr__(self) -> str:
        return f"<ChatSession(id={self.id}, title={self.title}, status={self.status})>"


# ==============================================================================
# ChatMessage：对话消息表
# ==============================================================================
class ChatMessage(Base):
    """
    对话消息表

    说明：
        - 每条消息关联一个会话
        - sources 字段记录助手回答引用的知识切片或网页来源

    角色类型：
        - user：用户发送的消息
        - assistant：LLM 生成的回答
        - system：系统消息（如沉淀通知）
    """

    __tablename__ = "chat_messages"

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
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        comment="所属会话 ID",
    )

    # --------------------------------------------------------------------------
    # 消息内容
    # --------------------------------------------------------------------------
    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="消息角色：user/assistant/system",
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="消息内容",
    )
    sources: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="引用的知识切片/网页列表：[{id, title, document_id, score, url}]",
    )
    quiz_paper_id: Mapped[str | None] = mapped_column(
        String(36),
        nullable=True,
        default=None,
        comment="关联试卷 ID（模拟练习消息），普通消息为 NULL",
    )
    document_ids: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="用户消息通过 @ 选择的文档 ID 列表；练习模式上下文连贯的回退依据",
    )

    # --------------------------------------------------------------------------
    # 时间戳
    # --------------------------------------------------------------------------
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="发送时间",
    )

    # --------------------------------------------------------------------------
    # 关联关系
    # --------------------------------------------------------------------------
    session: Mapped["ChatSession"] = relationship(
        back_populates="messages",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<ChatMessage(id={self.id}, role={self.role}, session_id={self.session_id})>"
