"""Chat application service."""

from __future__ import annotations

import logging
import inspect
from collections.abc import AsyncIterator, Callable
from typing import Any

from sqlalchemy import func

from app.api.presenters.sse import format_sse_event
from app.domain.ports.chat import ChatRepository
from app.domain.ports.chat_workflow import ChatWorkflowRunner
from app.domain.ports.database import DatabaseSession
from app.domain.ports.memory import MemoryCapturePort
from app.schemas.memory import L0Context, MemoryActivity
from app.infrastructure.chat import ChatMessage, ChatSession
from app.infrastructure.chat_repository import SQLAlchemyChatRepository
from app.schemas.base import PaginatedData
from app.schemas.chat import ChatMessageResponse, ChatSessionDetail, ChatSessionResponse
from app.infrastructure.setup_config import friendly_error_message


logger = logging.getLogger(__name__)


class ChatService:
    def __init__(
        self,
        db: DatabaseSession,
        workflow_runner_factory: Callable[[DatabaseSession, list[str]], ChatWorkflowRunner | Any] | None = None,
        chat_repository: ChatRepository | None = None,
        memory_capture: MemoryCapturePort | None = None,
        memory_pipeline: Any | None = None,
        subject_resolver: Callable[[list[str]], str | None] | None = None,
    ):
        self.db = db
        self.workflow_runner_factory = workflow_runner_factory
        self._chat_repository = chat_repository or SQLAlchemyChatRepository(db)
        self.memory_capture = memory_capture
        self.memory_pipeline = memory_pipeline
        self._subject_resolver = subject_resolver

    def create_session(self, title: str | None = None) -> ChatSessionResponse:
        session = ChatSession(title=title or "新对话", status="active")
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return self._session_response(session, 0)

    def list_sessions(self, page: int, page_size: int) -> PaginatedData[ChatSessionResponse]:
        total = self.db.query(func.count(ChatSession.id)).scalar() or 0
        rows = (
            self.db.query(ChatSession)
            .order_by(ChatSession.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        items = []
        for session in rows:
            count = (
                self.db.query(func.count(ChatMessage.id))
                .filter(ChatMessage.session_id == session.id)
                .scalar()
                or 0
            )
            items.append(self._session_response(session, count))
        total_pages = (total + page_size - 1) // page_size if total else 0
        return PaginatedData(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    def get_session(self, session_id: str) -> ChatSessionDetail | None:
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session is None:
            return None
        messages = (
            self.db.query(ChatMessage)
            .filter(ChatMessage.session_id == session_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        return ChatSessionDetail(
            **self._session_response(session, len(messages)).model_dump(),
            capabilities=list(session.capabilities or []),
            messages=[ChatMessageResponse.model_validate(message) for message in messages],
        )

    def delete_session(self, session_id: str) -> bool:
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session is None:
            return False
        self.db.delete(session)
        self.db.commit()
        return True

    def update_session_capabilities(
        self, session_id: str, capabilities: list[str]
    ) -> ChatSessionResponse | None:
        """更新会话默认能力；会话不存在返回 None。"""
        session = self.db.query(ChatSession).filter(ChatSession.id == session_id).first()
        if session is None:
            return None
        session.capabilities = capabilities or []
        self.db.commit()
        self.db.refresh(session)
        count = (
            self.db.query(func.count(ChatMessage.id))
            .filter(ChatMessage.session_id == session_id)
            .scalar()
            or 0
        )
        return self._session_response(session, count)

    def stream_message(
        self,
        session_id: str,
        content: str,
        document_ids: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> AsyncIterator[str]:
        return self._stream_message(session_id, content, document_ids, capabilities)

    async def _stream_message(
        self,
        session_id: str,
        content: str,
        document_ids: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> AsyncIterator[str]:
        session = self._chat_repository.get_session(session_id)
        if session is None:
            yield format_sse_event("error", {"message": "会话不存在"})
            return

        selected = set(capabilities or [])
        # 会话默认能力同步：最近一次消息用到的能力自动成为会话默认
        # （随用户消息同一事务提交，待引入 UOW 后交由工作单元接管）。
        session.capabilities = sorted(selected)
        effective_document_ids = self._get_effective_document_ids(
            session_id, document_ids, selected
        )
        self._save_user_message(session, content, effective_document_ids)
        self._capture(session_id, "user", content, self._memory_context(selected, effective_document_ids))

        yield format_sse_event("status", {"status": "thinking"})

        try:
            if self.workflow_runner_factory is None:
                raise RuntimeError("聊天工作流运行器未配置")

            runner_or_coro = self.workflow_runner_factory(self.db, sorted(selected))
            if inspect.isawaitable(runner_or_coro):
                runner = await runner_or_coro
            else:
                runner = runner_or_coro

            answer_parts: list[str] = []
            sources: list[dict] = []
            quiz_paper_id: str | None = None
            stream_kwargs = {
                "document_ids": effective_document_ids,
            }
            stream_kwargs["capabilities"] = sorted(selected)
            async for event in runner.stream_events(
                session_id,
                content,
                **stream_kwargs,
            ):
                if event.type == "status":
                    yield format_sse_event("status", {"status": str(event.data)})
                    continue
                if event.type == "step":
                    # 执行步骤日志：仅用于前端流式展示，不写入最终消息内容。
                    yield format_sse_event("step", event.data)
                    continue
                if event.type == "quiz_token":
                    # 出题生成过程的流式文本：仅用于前端实时展示，
                    # 不进入最终 assistant 消息内容（最终内容为 agent 回复）。
                    yield format_sse_event("quiz_token", {"token": str(event.data)})
                    continue
                if event.type == "quiz_reset":
                    yield format_sse_event("quiz_reset", {})
                    continue
                if event.type == "sources":
                    sources = event.data
                    yield format_sse_event("sources", {"sources": sources})
                    continue
                if event.type == "quiz":
                    # 模拟练习试卷载荷：一次性下发，前端据此渲染内联卡片。
                    payload = event.data
                    if isinstance(payload, dict) and payload.get("paper_id"):
                        quiz_paper_id = str(payload["paper_id"])
                    yield format_sse_event("quiz", payload)
                    continue
                if event.type == "token":
                    token = str(event.data)
                    answer_parts.append(token)
                    yield format_sse_event("token", {"token": token})

            answer = "".join(answer_parts).strip()
            if not answer:
                yield format_sse_event("error", {"message": "模型未生成内容"})
                return

            assistant = self._save_assistant_message(
                session, answer, sources, quiz_paper_id
            )
            self._capture(session_id, "assistant", answer, self._memory_context(selected, effective_document_ids, quiz_paper_id))
            self._notify_memory(session_id)

            yield format_sse_event(
                "done",
                {
                    "message_id": assistant.id,
                    "sources": sources,
                    "quiz_paper_id": quiz_paper_id,
                },
            )
        except Exception as exc:
            # 事务边界：项目暂无 UnitOfWork，提交在仓储内、回滚在此兜底；
            # 待引入 UOW 后，此处的 commit/rollback 统一移交工作单元接管。
            self.db.rollback()
            yield format_sse_event("error", {"message": friendly_error_message(exc)})

    def _get_effective_document_ids(
        self,
        session_id: str,
        document_ids: list[str] | None,
        selected: set[str],
    ) -> list[str]:
        """练习模式上下文连贯：本次请求未通过 @ 携带文档时，回退到本会话
        最近一次 @ 选择的文档 ID，避免 agent 无法注入文件内容。"""
        effective_document_ids = list(document_ids or [])
        if "practice" in selected and not effective_document_ids:
            last_with_docs = self._chat_repository.find_latest_user_message_with_documents(
                session_id
            )
            if last_with_docs is not None and last_with_docs.document_ids:
                effective_document_ids = list(last_with_docs.document_ids)
        return effective_document_ids

    def _save_user_message(
        self,
        session: ChatSession,
        content: str,
        effective_document_ids: list[str],
    ) -> None:
        """持久化用户消息，并刷新会话标题 / updated_at。"""
        if session.title == "新对话":
            session.title = content[:50] + ("..." if len(content) > 50 else "")
        self._chat_repository.create_user_message(
            session, content, effective_document_ids or None
        )

    def _save_assistant_message(
        self,
        session: ChatSession,
        answer: str,
        sources: list[dict],
        quiz_paper_id: str | None,
    ) -> ChatMessage:
        """持久化助手消息，返回带生成 ID 的实体。"""
        return self._chat_repository.create_assistant_message(
            session, answer, sources or None, quiz_paper_id
        )

    def _capture(self, session_id: str, role: str, content: str, context: L0Context) -> None:
        """旁路捕获到长期记忆 L0；失败不阻断对话（捕获非关键路径）。"""
        if self.memory_capture is None:
            return
        try:
            try:
                self.memory_capture.capture_message(session_id, role, content, context)
            except TypeError:
                # Backward-compatible with injected capture adapters predating L0 context.
                self.memory_capture.capture_message(session_id, role, content)
        except Exception:  # noqa: BLE001 - 旁路捕获失败不得影响对话
            logger.exception("L0 捕获失败: session=%s role=%s", session_id, role)

    def _memory_context(self, selected: set[str], document_ids: list[str], quiz_paper_id: str | None = None) -> L0Context:
        activity = (MemoryActivity.practice if "practice" in selected else
                    MemoryActivity.knowledge if "knowledge" in selected else
                    MemoryActivity.conversation)
        subject = self._subject_resolver(document_ids) if self._subject_resolver else None
        return L0Context(
            activity=activity,
            subject=subject,
            capabilities=sorted(selected),
            document_ids=list(document_ids),
            quiz_paper_id=quiz_paper_id,
        )

    def _notify_memory(self, session_id: str) -> None:
        """每轮对话完成后触发 L1 记忆提取；失败不阻断对话。"""
        if self.memory_pipeline is None:
            return
        try:
            self.memory_pipeline.notify_conversation(session_id)
        except Exception:  # noqa: BLE001 - 触发失败不影响对话
            logger.exception("L1 触发失败: session=%s", session_id)

    @staticmethod
    def _session_response(session: ChatSession, message_count: int) -> ChatSessionResponse:
        return ChatSessionResponse(
            id=session.id,
            title=session.title,
            status=session.status,
            message_count=message_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
        )
