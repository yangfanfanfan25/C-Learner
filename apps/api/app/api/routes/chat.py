"""Chat API routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.domain.chat_service import ChatService
from app.domain.memory_pipeline import L1Runner, MemoryPipelineQueue
from app.domain.memory_scene_runner import L2Runner
from app.domain.memory_persona_runner import L3Runner
from app.domain.ports.chat_workflow import ChatWorkflowRunner
from app.domain.ports.database import DatabaseSession
from app.domain.ports.prompt_enhancer import PromptEnhancer
from app.domain.quiz_service import QuizPaperService
from app.infrastructure.deepagents.chat_workflow import DeepAgentsChatWorkflowRunner
from app.infrastructure.deepagents.checkpoint import get_chat_checkpointer
from app.infrastructure.deepagents.practice_workflow import DeepAgentsPracticeWorkflowRunner
from app.infrastructure.documents import SQLAlchemyDocumentRepository
from app.infrastructure.embeddings import get_embedding_provider
from app.infrastructure.files.quiz_file_storage import get_local_quiz_file_storage
from app.infrastructure.knowledge_reader import SQLAlchemyKnowledgeDocumentReader
from app.infrastructure.llm.prompt_enhancer import LangChainPromptEnhancer
from app.infrastructure.llm.provider import create_chat_model
from app.infrastructure.memory.capture import MemoryCaptureService, get_l1_memory_vector_store
from app.infrastructure.memory.dedup import LangChainDedupJudge
from app.infrastructure.memory.extractor import LangChainAtomExtractor
from app.infrastructure.memory.files import LocalMemoryFileStorage
from app.infrastructure.memory.journal import JsonlJournalStore
from app.infrastructure.memory.recall import MemoryRecallService
from app.infrastructure.memory.persona import LangChainPersonaGenerator
from app.infrastructure.memory.scene import LangChainSceneExtractor
from app.infrastructure.memory.scene_store import SceneBlockStore
from app.infrastructure.memory.sqlite_repository import SqliteMemoryRepository
from app.infrastructure.milvus import get_milvus_vector_store
from app.infrastructure.prompts import ChatSystemPromptProvider
from app.infrastructure.prompts.memory_prompts import MemoryPromptProvider
from app.infrastructure.sqlite.engine import get_db
from app.infrastructure.sqlite.provider import create_sqlite_provider
from app.infrastructure.web_search import ZhipuWebSearchProvider
from app.schemas.base import APIResponse, PaginatedData
from app.schemas.chat import (
    ChatMessageCreate,
    ChatSessionCapabilitiesUpdate,
    ChatSessionCreate,
    ChatSessionDetail,
    ChatSessionResponse,
    PromptEnhanceRequest,
    PromptEnhanceResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat"])

logger = logging.getLogger(__name__)


async def _create_workflow_runner(
    db: DatabaseSession,
    capabilities: list[str],
) -> ChatWorkflowRunner:
    """按模式装配聊天运行器：``retrieval``=知识检索，``practice``=模拟练习。

    所有外部依赖（LLM、checkpointer、embedding、向量库、知识读取、试卷服务等）
    在此组合根创建并注入。
    """
    settings = get_settings()
    model = create_chat_model()
    checkpointer = await get_chat_checkpointer()
    embedding_provider = get_embedding_provider(settings)
    vector_store = get_milvus_vector_store(settings)
    recall = _build_memory_recall(db, settings)
    document_repo = SQLAlchemyDocumentRepository(db)

    def resolve_subject(document_ids: list[str]) -> str | None:
        subjects = {
            record.course_name
            for document_id in document_ids
            if (record := document_repo.get_record(document_id)) is not None
            and record.course_name != "未分类"
        }
        return next(iter(subjects)) if len(subjects) == 1 else None

    web_search_provider = ZhipuWebSearchProvider(
        api_key=settings.zhipu_api_key,
        timeout_seconds=settings.web_search_timeout_seconds,
    )
    if "practice" in capabilities:
        return DeepAgentsPracticeWorkflowRunner(
            model=model,
            checkpointer=checkpointer,
            knowledge_reader=SQLAlchemyKnowledgeDocumentReader(
                SQLAlchemyDocumentRepository(db)
            ),
            quiz_service=QuizPaperService(
                db,
                get_local_quiz_file_storage(settings),
            ),
            quiz_generation_model=create_chat_model(),
            system_prompt_provider=ChatSystemPromptProvider(),
            web_search_provider=web_search_provider,
            web_search_max_results=settings.web_search_max_results,
            memory_recall=recall,
            subject_resolver=resolve_subject,
            anchor_memory=settings.chat_anchor_memory_enabled,
            anchor_every_n_turns=settings.chat_anchor_every_n_turns,
            anchor_min_new_tokens=settings.chat_anchor_min_new_tokens,
            anchor_max_anchor_chars=settings.chat_anchor_max_anchor_chars,
        )
    return DeepAgentsChatWorkflowRunner(
        model=model,
        checkpointer=checkpointer,
        embedding_provider=embedding_provider,
        vector_store=vector_store,
        web_search_provider=web_search_provider,
        system_prompt_provider=ChatSystemPromptProvider(),
        rag_top_k=settings.rag_top_k,
        web_search_max_results=settings.web_search_max_results,
        memory_recall=recall,
        subject_resolver=resolve_subject,
        anchor_memory=settings.chat_anchor_memory_enabled,
        anchor_every_n_turns=settings.chat_anchor_every_n_turns,
        anchor_min_new_tokens=settings.chat_anchor_min_new_tokens,
        anchor_max_anchor_chars=settings.chat_anchor_max_anchor_chars,
    )


def _build_memory_recall(db, settings) -> MemoryRecallService | None:
    """装配召回注入服务；失败返回 None（召回是旁路，不阻断对话）。"""
    try:
        sqlite_repo = SqliteMemoryRepository(db, create_sqlite_provider(settings))
        profile_root = settings.memory_profiles_path / "default"
        file_storage = LocalMemoryFileStorage(profile_root)
        return MemoryRecallService(
            atom_repo=sqlite_repo,
            vector_store=get_l1_memory_vector_store(settings),
            embedding=get_embedding_provider(settings),
            scene_store=SceneBlockStore(file_storage),
            file_storage=file_storage,
            score_threshold=settings.memory_recall_score_threshold,
            max_results=settings.memory_recall_max_results,
            max_chars_per_memory=settings.memory_recall_max_chars_per_memory,
            max_total_chars=settings.memory_recall_max_total_chars,
        )
    except Exception:  # noqa: BLE001
        logger.warning("记忆召回装配失败，降级为不启用", exc_info=True)
        return None


def get_prompt_enhancer() -> PromptEnhancer:
    return LangChainPromptEnhancer(create_chat_model())


def _build_memory_capture(db: Session, vector_store) -> MemoryCaptureService | None:
    """装配 L0 捕获服务；装配失败返回 None（记忆是旁路，不得阻断聊天）。"""
    try:
        settings = get_settings()
        sqlite_repo = SqliteMemoryRepository(db, create_sqlite_provider(settings))
        journal = JsonlJournalStore(settings.memory_conversations_path)
        embedding = get_embedding_provider(settings)
        return MemoryCaptureService(
            sqlite_repo=sqlite_repo,
            journal=journal,
            vector_store=vector_store,
            embedding=embedding,
        )
    except Exception:  # noqa: BLE001 - 旁路装配失败降级为不启用记忆
        logger.warning("记忆捕获装配失败，降级为不启用", exc_info=True)
        return None


_memory_pipeline: MemoryPipelineQueue | None = None


def _set_memory_pipeline(pipeline: MemoryPipelineQueue | None) -> None:
    """由 lifespan 注入进程级 L1 管线单例（跨请求共享的简化握手）。"""
    global _memory_pipeline
    _memory_pipeline = pipeline


def _build_memory_pipeline(db: Session) -> MemoryPipelineQueue | None:
    """装配 L1 提取管线（未启动）；装配失败返回 None（记忆是旁路，不得阻断聊天）。"""
    try:
        settings = get_settings()
        sqlite_repo = SqliteMemoryRepository(db, create_sqlite_provider(settings))
        journal = JsonlJournalStore(settings.memory_records_path)
        embedding = get_embedding_provider(settings)
        model = create_chat_model()
        extractor = LangChainAtomExtractor(model=model, prompt_provider=MemoryPromptProvider())
        dedup_judge = LangChainDedupJudge(model=model, prompt_provider=MemoryPromptProvider())
        profile_root = settings.memory_profiles_path / "default"
        scene_store = SceneBlockStore(LocalMemoryFileStorage(profile_root))
        l2_runner = L2Runner(
            atom_repo=sqlite_repo,
            extractor=LangChainSceneExtractor(
                model=model,
                scene_store=scene_store,
                scene_blocks_dir=str(profile_root / "scene_blocks"),
                max_scenes=settings.memory_max_scenes,
            ),
            delay_seconds=settings.memory_l2_delay_after_l1_seconds,
            min_interval_seconds=settings.memory_l2_min_interval_seconds,
            max_interval_seconds=settings.memory_l2_max_interval_seconds,
        )
        l3_runner = L3Runner(
            generator=LangChainPersonaGenerator(
                model=model,
                scene_store=scene_store,
                persona_dir=str(profile_root),
            ),
            trigger_every_n=settings.memory_l3_trigger_every_n,
        )
        runner = L1Runner(
            l0_repo=sqlite_repo,
            atom_repo=sqlite_repo,
            extractor=extractor,
            dedup_judge=dedup_judge,
            journal=journal,
            vector_store=get_l1_memory_vector_store(settings),
            embedding=embedding,
            generation_log_repo=sqlite_repo,
            batch_query=settings.memory_l1_batch_query,
            batch_process=settings.memory_l1_batch_process,
        )
        return MemoryPipelineQueue(
            runner=runner,
            l0_repo=sqlite_repo,
            every_n=settings.memory_l1_every_n,
            idle_timeout_seconds=settings.memory_l1_idle_timeout_seconds,
            l2_runner=l2_runner,
            l3_runner=l3_runner,
        )
    except Exception:  # noqa: BLE001 - 旁路装配失败降级为不启用
        logger.warning("L1 管线装配失败，降级为不启用", exc_info=True)
        return None


def get_chat_service(
    request: Request,
    db: Session = Depends(get_db),
) -> ChatService:
    document_repo = SQLAlchemyDocumentRepository(db)

    def resolve_subject(document_ids: list[str]) -> str | None:
        subjects = {
            record.course_name
            for document_id in document_ids
            if (record := document_repo.get_record(document_id)) is not None
            and record.course_name != "未分类"
        }
        return next(iter(subjects)) if len(subjects) == 1 else None

    return ChatService(
        db,
        workflow_runner_factory=_create_workflow_runner,
        memory_capture=_build_memory_capture(
            db,
            getattr(request.app.state, "memory_vector_store", None),
        ),
        memory_pipeline=_memory_pipeline,
        subject_resolver=resolve_subject,
    )


@router.post(
    "/prompts/enhance",
    response_model=APIResponse[PromptEnhanceResponse],
    summary="Enhance a chat prompt",
)
async def enhance_prompt(
    body: PromptEnhanceRequest,
    enhancer: PromptEnhancer = Depends(get_prompt_enhancer),
) -> APIResponse[PromptEnhanceResponse]:
    try:
        content = await enhancer.enhance(body.content)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="提示词增强服务暂时不可用") from exc
    return APIResponse(data=PromptEnhanceResponse(content=content), message="提示词增强成功")


@router.post(
    "/sessions",
    response_model=APIResponse[ChatSessionResponse],
    summary="Create a chat session",
)
def create_session(
    body: ChatSessionCreate,
    service: ChatService = Depends(get_chat_service),
) -> APIResponse[ChatSessionResponse]:
    return APIResponse(data=service.create_session(body.title), message="会话创建成功")


@router.get(
    "/sessions",
    response_model=APIResponse[PaginatedData[ChatSessionResponse]],
    summary="List chat sessions",
)
def list_sessions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: ChatService = Depends(get_chat_service),
) -> APIResponse[PaginatedData[ChatSessionResponse]]:
    return APIResponse(data=service.list_sessions(page, page_size))


@router.get(
    "/sessions/{session_id}",
    response_model=APIResponse[ChatSessionDetail],
    summary="Get a chat session with messages",
)
def get_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> APIResponse[ChatSessionDetail]:
    detail = service.get_session(session_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return APIResponse(data=detail)


@router.put(
    "/sessions/{session_id}/capabilities",
    response_model=APIResponse[ChatSessionResponse],
    summary="Update session default capabilities",
)
def update_session_capabilities(
    session_id: str,
    body: ChatSessionCapabilitiesUpdate,
    service: ChatService = Depends(get_chat_service),
) -> APIResponse[ChatSessionResponse]:
    session = service.update_session_capabilities(session_id, body.capabilities)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return APIResponse(data=session, message="会话默认能力已更新")


@router.delete(
    "/sessions/{session_id}",
    response_model=APIResponse[bool],
    summary="Delete a chat session",
)
def delete_session(
    session_id: str,
    service: ChatService = Depends(get_chat_service),
) -> APIResponse[bool]:
    if not service.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return APIResponse(data=True, message="删除成功")


@router.post(
    "/sessions/{session_id}/messages/stream",
    summary="Send a message and stream the answer by SSE",
)
def stream_message(
    session_id: str,
    body: ChatMessageCreate,
    service: ChatService = Depends(get_chat_service),
) -> StreamingResponse:
    return StreamingResponse(
        service.stream_message(
            session_id=session_id,
            content=body.content,
            document_ids=body.document_ids,
            capabilities=body.capabilities,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
