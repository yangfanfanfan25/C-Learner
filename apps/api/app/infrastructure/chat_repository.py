# ==============================================================================
# 聊天持久化适配器：ChatRepository 的 SQLite 实现
# ==============================================================================
# 对接 domain/ports/chat.py 协议，封装 chat_sessions / chat_messages 的
# 查询与写入细节；领域服务不再直接调用 SQLAlchemy API。
# ==============================================================================

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.ports.database import DatabaseSession
from app.infrastructure.chat import ChatMessage, ChatSession


def _utcnow() -> datetime:
    """返回当前 UTC 时间。"""
    return datetime.now(timezone.utc)


class SQLAlchemyChatRepository:
    """SQLite implementation of the chat persistence port.

    事务边界：当前无 UnitOfWork，采用「每操作即提交」策略（与
    ``SQLAlchemyDocumentRepository`` 一致）；待引入 UOW 后应改为
    由工作单元统一提交 / 回滚。
    """

    def __init__(self, db: DatabaseSession) -> None:
        self.db = db

    def get_session(self, session_id: str) -> ChatSession | None:
        """按 ID 查询会话。"""
        return self.db.query(ChatSession).filter(ChatSession.id == session_id).first()

    def find_latest_user_message_with_documents(
        self, session_id: str
    ) -> ChatMessage | None:
        """本会话最近一条带 document_ids 的 user 消息。"""
        return (
            self.db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == session_id,
                ChatMessage.role == "user",
                ChatMessage.document_ids.isnot(None),
            )
            .order_by(ChatMessage.created_at.desc())
            .first()
        )

    def create_user_message(
        self,
        session: ChatSession,
        content: str,
        document_ids: list[str] | None,
    ) -> ChatMessage:
        """落库用户消息并刷新会话 updated_at（单事务提交）。"""
        message = ChatMessage(
            session_id=session.id,
            role="user",
            content=content,
            document_ids=document_ids,
        )
        self.db.add(message)
        session.updated_at = _utcnow()
        self.db.commit()
        return message

    def create_assistant_message(
        self,
        session: ChatSession,
        answer: str,
        sources: list[dict] | None,
        quiz_paper_id: str | None,
    ) -> ChatMessage:
        """落库助手消息并刷新会话 updated_at（单事务提交），返回带 ID 的实体。"""
        message = ChatMessage(
            session_id=session.id,
            role="assistant",
            content=answer,
            sources=sources,
            quiz_paper_id=quiz_paper_id,
        )
        self.db.add(message)
        session.updated_at = _utcnow()
        self.db.commit()
        self.db.refresh(message)
        return message
