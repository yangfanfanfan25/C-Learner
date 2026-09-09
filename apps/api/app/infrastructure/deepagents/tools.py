"""deepagents 智能体工具定义。

职责：把知识库检索与联网搜索封装为智能体可调用的 LangChain 工具。
工具通过构造函数注入的外部依赖（embedding provider、向量库、联网搜索 provider）
执行检索；工具生命周期和返回正文由 LangGraph 原生 ``tools`` 流输出，
结构化来源通过 ``get_stream_writer`` 写入 custom 事件流，供运行时转发为 SSE。

本模块只定义工具与来源累积器，不包含图结构搭建或业务编排。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langchain_core.tools import StructuredTool
from langgraph.config import get_stream_writer

from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.semantic_store import SemanticVectorStore
from app.domain.ports.web_search import WebSearchProvider

logger = logging.getLogger(__name__)

_KNOWLEDGE_CONTENT_MAX = 1800
"""单个知识切片注入模型的正文长度上限，避免上下文膨胀。"""


def stream_emit(kind: str, data: Any) -> None:
    """通过 LangGraph 原生 custom 事件通道实时推送工具内部事件。

    仅在图中执行（工作流 ``stream_mode`` 含 ``custom``）时生效；
    直接调用工具（无图运行时，``get_stream_writer`` 抛 ``KeyError``）为空操作，
    保证工具可独立测试。
    """
    try:
        writer = get_stream_writer()
    except KeyError:
        return
    if writer is not None:
        writer({"kind": kind, "data": data})


class SourcesCollector:
    """线程内共享的来源累积器，去重后供流式运行时按需读取。

    工具通过 custom 事件分批上报来源（``kind="sources"``）；流式循环用
    本累积器合并去重后发出 SSE ``sources`` 事件（保持“累积完整列表”语义）。
    """

    def __init__(self) -> None:
        self._sources: list[dict[str, Any]] = []
        self._seen: set[str] = set()
        self._dirty = False

    def add(self, sources: list[dict[str, Any]]) -> None:
        """追加来源，按 ``id``/``url`` 去重。"""
        for source in sources:
            source_id = str(source.get("id") or source.get("url") or source)
            if source_id in self._seen:
                continue
            self._seen.add(source_id)
            self._sources.append(source)
            self._dirty = True

    def drain(self) -> list[dict[str, Any]]:
        """返回新增来源；无新增时返回空列表。"""
        if not self._dirty:
            return []
        self._dirty = False
        return list(self._sources)


def build_knowledge_search_tool(
    embedding_provider: EmbeddingProvider,
    vector_store: SemanticVectorStore,
    top_k: int,
) -> StructuredTool:
    """构建知识库检索工具。

    检索失败时抛出 ``RuntimeError``（与旧 LangGraph 流程一致，向调用方暴露
    知识库基础设施故障，而非静默降级为“无结果”）。

    工具生命周期与返回值由 LangGraph 原生 ``tools`` stream mode 输出；
    本工具仅通过 custom 通道补充结构化来源。
    """

    async def search_knowledge(query: str) -> str:
        """检索本地个人知识库，返回与 query 语义最相关的知识切片。"""
        try:
            query_vector = await asyncio.to_thread(
                embedding_provider.embed_query,
                query,
            )
            hits = await vector_store.search(query_vector, top_k)
        except Exception as exc:
            logger.error("Semantic retrieval failed: %s: %s", type(exc).__name__, exc)
            raise RuntimeError(f"知识库检索失败：{type(exc).__name__}") from exc
        if not hits:
            return "未在本地知识库中找到相关内容。"

        context = "\n\n---\n\n".join(
            f"## {hit.title}\n\n[Chapter: {hit.chapter}] [Section: {hit.section}]\n\n"
            f"{hit.content[:_KNOWLEDGE_CONTENT_MAX]}"
            for hit in hits
        )
        stream_emit(
            "sources",
            [
                {
                    "id": hit.chunk_id,
                    "title": hit.title,
                    "document_id": hit.document_id,
                    "score": round(hit.score, 4),
                }
                for hit in hits
            ],
        )
        return context

    return StructuredTool.from_function(
        name="search_knowledge",
        description=(
            "检索本地个人知识库。回答用户问题前应优先调用本工具，"
            "以知识库中检索到的内容作为主要依据。"
        ),
        coroutine=search_knowledge,
    )


def build_web_search_tool(
    web_search_provider: WebSearchProvider,
    max_results: int,
) -> StructuredTool:
    """构建联网搜索工具。

    联网搜索失败时降级返回提示文本（与旧 ``_web_search_node`` 一致），
    不中断整体回答流程。

    工具生命周期与返回值由 LangGraph 原生 ``tools`` stream mode 输出；
    本工具仅通过 custom 通道补充结构化来源。
    """

    async def search_web(query: str) -> str:
        """联网搜索，返回与 query 相关的互联网信息。"""
        try:
            result = await web_search_provider.search(
                query=query,
                max_results=max_results,
            )
        except Exception as exc:
            logger.warning("Web search unavailable: %s: %s", type(exc).__name__, exc)
            return "Web search is temporarily unavailable."
        stream_emit(
            "sources",
            [
                {"id": source.id, "title": source.title, "url": source.url}
                for source in result.sources
            ],
        )
        return result.context

    return StructuredTool.from_function(
        name="search_web",
        description=(
            "联网搜索互联网信息。当知识库内容不足以回答、或需要最新信息时使用，"
            "结合知识库检索结果给出综合回答。"
        ),
        coroutine=search_web,
    )
