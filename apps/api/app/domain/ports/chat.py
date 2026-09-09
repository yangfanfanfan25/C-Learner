"""Chat persistence port used by the chat service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.infrastructure.chat import ChatMessage, ChatSession


class ChatRepository(Protocol):
    """聊天持久化端口（返回 ORM 实体）。

    服务依赖本协议而非直接操作数据库 API；具体查询 / 落库 / 提交细节由
    基础设施层适配器实现（当前为 ``SQLAlchemyChatRepository``）。
    """

    def get_session(self, session_id: str) -> ChatSession | None:
        """按 ID 查询会话；不存在返回 ``None``。"""
        ...

    def find_latest_user_message_with_documents(self, session_id: str) -> ChatMessage | None:
        """返回本会话最近一条带 ``document_ids`` 的 user 消息（练习模式回退依据）。"""
        ...

    def create_user_message(
        self,
        session: ChatSession,
        content: str,
        document_ids: list[str] | None,
    ) -> ChatMessage:
        """落库一条 user 消息，刷新会话 ``updated_at`` 并提交。"""
        ...

    def create_assistant_message(
        self,
        session: ChatSession,
        answer: str,
        sources: list[dict] | None,
        quiz_paper_id: str | None,
    ) -> ChatMessage:
        """落库一条 assistant 消息，刷新会话 ``updated_at`` 并提交，返回带 ID 的实体。"""
        ...
