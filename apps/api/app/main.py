# ==============================================================================
# FastAPI 应用入口
# ==============================================================================
# 功能：
#   - 应用生命周期管理（启动/关闭）
#   - 路由注册
#   - 数据库初始化（通过 Alembic 迁移）
#
# 启动流程：
#   1. 创建数据目录
#   2. 运行 Alembic 迁移，初始化/更新 SQLite schema
#   3. 注册各领域路由
#
# 关闭流程：
#   1. 释放 SQLAlchemy 引擎连接池
# ==============================================================================

import subprocess
import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI

from app.api.routes.health import router as health_router
from app.api.routes.setup import router as setup_router
from app.api.routes.chat import router as chat_router
from app.api.routes.documents import router as documents_router
from app.api.routes.domains import router as domains_router
from app.api.routes.chapters import router as chapters_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.exam_records import router as exam_records_router
from app.api.routes.review import router as review_router
from app.api.routes.quiz import router as quiz_router
from app.core.config import get_settings
from app.infrastructure.embeddings import reset_embedding_provider, warmup_embedding_provider
from app.infrastructure.memory.sqlite_repository import init_fts
from app.infrastructure.milvus import create_memory_vector_store
from app.infrastructure.sqlite.provider import create_sqlite_provider

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期处理器。

    启动时：
        - 确保数据目录存在
        - 运行 Alembic 迁移，初始化/更新 SQLite schema

    关闭时：
        - 释放 SQLAlchemy 引擎连接池
    """
    settings = get_settings()

    # 确保数据目录存在
    settings.data_root.mkdir(parents=True, exist_ok=True)
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.milvus_lite_path.parent.mkdir(parents=True, exist_ok=True)
    settings.files_path.mkdir(parents=True, exist_ok=True)

    # 运行 Alembic 迁移
    alembic_dir = Path(__file__).parent.parent / "alembic"
    if alembic_dir.exists():
        try:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                cwd=str(alembic_dir.parent),
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            # 记录错误但不崩溃 — 允许手动迁移
            print(f"警告：Alembic 迁移失败：{e.stderr}")

    # 预热并保留进程级 Embedding provider，避免首个 Chat 请求承担模型加载成本。
    try:
        await warmup_embedding_provider(settings)
    except Exception as exc:  # noqa: BLE001 - 启动可继续，首请求会重试并暴露真实错误
        logger.warning("Embedding provider warmup failed; first request will retry: %s", exc)

    # 文档处理队列：懒初始化（首个上传请求时构建），此处仅预留占位
    app.state.document_queue = None
    try:
        app.state.memory_vector_store = create_memory_vector_store(settings)
    except Exception as exc:  # noqa: BLE001 - memory vectors are optional
        logger.warning("Memory vector store initialization failed: %s", exc)
        app.state.memory_vector_store = None

    # 长期记忆：初始化 L0 FTS5 虚拟表（raw DDL，不进 Alembic）
    try:
        init_fts(create_sqlite_provider(settings))
    except Exception as exc:  # noqa: BLE001 - 记忆初始化失败不阻断启动
        logger.warning("记忆 FTS5 初始化失败: %s", exc)

    # 长期记忆 L1：进程级管线单例（独立 Session 供后台 worker 使用），
    # 装配成功后 start() 并注入 chat 路由的模块级握手变量供请求侧 notify。
    try:
        from app.api.routes.chat import _build_memory_pipeline, _set_memory_pipeline
        from app.infrastructure.sqlite.engine import get_session_factory

        _memory_db = get_session_factory()()
        pipeline = _build_memory_pipeline(_memory_db)
        if pipeline is not None:
            app.state.memory_pipeline = pipeline
            pipeline.start()
            _set_memory_pipeline(pipeline)
    except Exception as exc:  # noqa: BLE001 - L1 启动失败不阻断启动
        logger.warning("L1 管线启动失败: %s", exc)

    yield

    # 关闭：停止文档处理队列 worker，释放 SQLAlchemy 引擎
    queue = getattr(app.state, "document_queue", None)
    if queue is not None:
        await queue.stop()
    from app.infrastructure.deepagents.checkpoint import close_chat_checkpointer
    from app.infrastructure.milvus import close_milvus_vector_store
    from app.infrastructure.sqlite.engine import dispose_engine
    await close_chat_checkpointer()
    close_milvus_vector_store()
    memory_store = getattr(app.state, "memory_vector_store", None)
    if memory_store is not None:
        memory_store.close()
    # L1 记忆管线：先停止 worker，再关闭 L1 向量库
    pipeline = getattr(app.state, "memory_pipeline", None)
    if pipeline is not None:
        await pipeline.stop()
    from app.infrastructure.memory.capture import close_l1_memory_vector_store
    close_l1_memory_vector_store()
    reset_embedding_provider()
    dispose_engine()


def create_app() -> FastAPI:
    """创建 FastAPI 应用实例。

    返回：
        配置好的 FastAPI 应用
    """
    settings = get_settings()
    app = FastAPI(
        title=settings.service_name,
        lifespan=lifespan,
    )

    # 注册路由
    app.include_router(health_router)
    app.include_router(setup_router, prefix="/api")
    app.include_router(chat_router, prefix="/api")
    # exam_router 已替换为 exam_records_router
    app.include_router(documents_router, prefix="/api")
    app.include_router(domains_router, prefix="/api")
    app.include_router(chapters_router, prefix="/api")
    app.include_router(knowledge_router, prefix="/api")
    app.include_router(exam_records_router, prefix="/api")
    app.include_router(review_router, prefix="/api")
    app.include_router(quiz_router, prefix="/api")

    return app


app = create_app()
