"""deepagents 模拟练习工作流。

职责：用 ``create_deep_agent`` 组装一个出题智能体运行器：

- 出题依据的文档由前端 ``@`` 选择（``document_ids`` 随请求透传），
  ``generate_quiz_paper`` 工具按 ID 直接读取已入库知识内容注入上下文出题，
  **不再进行 RAG 检索**（练习模式不提供 ``search_knowledge`` 工具）。
- ``generate_quiz_paper`` 内部读取知识内容、生成试卷（JSON 解析 + schema 校验）、
  落库并写出 md/json 导出文件，向 agent 返回简短结果摘要。
- 流式事件：``status``（loading_knowledge / generating_quiz）、``step``、
  ``quiz_token``（出题过程文本，随模型输出逐条推送）、``token``（agent 的最终简短回复）、
  ``quiz``（试卷载荷一次性下发）。

与检索运行器共用 deepagents 架构（``SummarizationMiddleware`` + checkpointer +
HarnessProfile 注册）；提示词全部来自注入的 ``SystemPromptProvider``，不内嵌在本模块。

流式采用框架原生通道：``stream_mode=["messages", "tools", "custom"]`` +
``version="v2"``。工具生命周期和结果使用 ``tools`` 通道；出题模型文本与重试清理
使用 ``get_stream_writer`` 上报 custom 事件，主循环逐条转发到前端。
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain.agents.middleware import ToolCallLimitMiddleware

from deepagents import create_deep_agent
from deepagents.backends import StateBackend
from deepagents.middleware.summarization import SummarizationMiddleware

from app.domain.ports.chat_workflow import ChatWorkflowEvent
from app.domain.ports.memory import MemoryRecallPort
from app.domain.ports.knowledge_reader import KnowledgeDocumentReader
from app.domain.ports.prompts import SystemPromptProvider
from app.domain.quiz_service import QuizPaperService
from app.infrastructure.deepagents.chat_workflow import (
    _ensure_rag_harness_profile,
    content_tokens,
    tool_stream_step,
)
from app.infrastructure.deepagents.quiz_tools import (
    QuizCollector,
    build_generate_quiz_tool,
)
from app.domain.ports.web_search import WebSearchProvider
from app.infrastructure.deepagents.tools import SourcesCollector, build_web_search_tool
from app.infrastructure.deepagents.chat_workflow import _append_recall_blocks, _prepend_memories
from app.schemas.memory import RecallContext
from app.infrastructure.deepagents.anchor_memory import AnchorMemoryMiddleware


class DeepAgentsPracticeWorkflowRunner:
    """基于 deepagents 的模拟练习（出题）运行器。

    依赖全部通过构造函数注入：模型、checkpointer、知识读取、试卷服务、
    出题模型、提示词提供者。出题依据文档 ID 按轮次传入（``stream_events``）。
    """

    def __init__(
        self,
        model: BaseChatModel,
        checkpointer: Any,
        knowledge_reader: KnowledgeDocumentReader,
        quiz_service: QuizPaperService,
        quiz_generation_model: Any,
        system_prompt_provider: SystemPromptProvider,
        web_search_provider: WebSearchProvider | None = None,
        web_search_max_results: int = 5,
        memory_recall: MemoryRecallPort | None = None,
        subject_resolver: Callable[[list[str]], str | None] | None = None,
        anchor_memory: bool = True,
        anchor_every_n_turns: int = 10,
        anchor_min_new_tokens: int = 2000,
        anchor_max_anchor_chars: int = 2000,
    ):
        self.model = model
        self.checkpointer = checkpointer
        self.knowledge_reader = knowledge_reader
        self.quiz_service = quiz_service
        self.quiz_generation_model = quiz_generation_model
        self.system_prompt_provider = system_prompt_provider
        self.web_search_provider = web_search_provider
        self.web_search_max_results = web_search_max_results
        self.memory_recall = memory_recall
        self.subject_resolver = subject_resolver
        self.anchor_memory = anchor_memory
        self.anchor_every_n_turns = anchor_every_n_turns
        self.anchor_min_new_tokens = anchor_min_new_tokens
        self.anchor_max_anchor_chars = anchor_max_anchor_chars
        _ensure_rag_harness_profile(model)

    async def stream_events(
        self,
        session_id: str,
        question: str,
        document_ids: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> AsyncIterator[ChatWorkflowEvent]:
        quiz_collector = QuizCollector()
        sources_collector = SourcesCollector()
        use_web_search = 'web_search' in (capabilities or [])
        recall = await self._recall(session_id, question, document_ids or [])
        agent = self._build_agent(
            session_id,
            document_ids or [],
            quiz_collector,
            use_web_search,
            recall,
        )
        config = {"configurable": {"thread_id": session_id}}
        input_state = {"messages": [HumanMessage(content=_prepend_memories(question, recall))]}

        yield ChatWorkflowEvent("status", "loading_knowledge")

        generating_emitted = False
        active_tool_calls: dict[str, dict[str, Any]] = {}
        # 框架原生流式：messages=agent 消息流，tools=工具生命周期与输出，
        # custom=出题模型 token/reset。
        async for chunk in agent.astream(
            input_state,
            config=config,
            stream_mode=["messages", "tools", "custom"],
            version="v2",
        ):
            if chunk["type"] == "tools":
                step = tool_stream_step(chunk["data"], active_tool_calls)
                if step is None:
                    continue
                if step["kind"] == "tool_start" and not generating_emitted:
                    generating_emitted = True
                    yield ChatWorkflowEvent("status", "generating_quiz")
                yield ChatWorkflowEvent("step", step)
                continue

            if chunk["type"] == "custom":
                payload = chunk["data"]
                kind = payload.get("kind")
                if kind == "quiz_token":
                    yield ChatWorkflowEvent("quiz_token", payload.get("data"))
                elif kind == "quiz_reset":
                    yield ChatWorkflowEvent("quiz_reset", None)
                elif kind == "sources":
                    sources_collector.add(payload.get("data") or [])
                    new_sources = sources_collector.drain()
                    if new_sources:
                        yield ChatWorkflowEvent("sources", new_sources)
                continue

            # messages 模式：data 为 (message_chunk, metadata) 元组
            event = chunk["data"]
            chunk, metadata = event[0], event[1]
            node = metadata.get("langgraph_node") if isinstance(metadata, dict) else None

            # 试卷载荷（工具完成后一次性写入收集器）随 agent 事件回传。
            quiz_payload = quiz_collector.drain()
            if quiz_payload:
                yield ChatWorkflowEvent("quiz", quiz_payload)

            if node == "tools" or isinstance(chunk, ToolMessage):
                continue

            # 逐 token 输出 agent 的最终简短回复；完整试卷只走 quiz 事件。
            for token in content_tokens(getattr(chunk, "content", "")):
                yield ChatWorkflowEvent("token", token)

        # 兜底：流结束后仍可能残留未回传的试卷载荷。
        trailing_quiz = quiz_collector.drain()
        if trailing_quiz:
            yield ChatWorkflowEvent("quiz", trailing_quiz)

    def _build_agent(
        self,
        session_id: str,
        document_ids: list[str],
        quiz_collector: QuizCollector,
        use_web_search: bool,
        recall: RecallContext | None = None,
    ):
        tools: list[Any] = []
        if use_web_search and self.web_search_provider is not None:
            tools.append(build_web_search_tool(self.web_search_provider, self.web_search_max_results))
        tools.append(
            build_generate_quiz_tool(
                session_id=session_id,
                document_ids=document_ids,
                knowledge_reader=self.knowledge_reader,
                quiz_service=self.quiz_service,
                quiz_generation_model=self.quiz_generation_model,
                prompt_provider=self.system_prompt_provider,
                collector=quiz_collector,
            ),
        )

        summarization = SummarizationMiddleware(
            model=self.model,
            backend=StateBackend(),
            trigger=("tokens", 50000),
            keep=("messages", 8),
            summary_prompt=self.system_prompt_provider.summarization_prompt(),
        )

        middleware: list[Any] = [summarization]
        if self.anchor_memory:
            middleware.insert(
                0,
                AnchorMemoryMiddleware(
                    model=self.model,
                    extract_prompt=self.system_prompt_provider.anchor_extraction_prompt(),
                    every_n_turns=self.anchor_every_n_turns,
                    min_new_tokens=self.anchor_min_new_tokens,
                    max_anchor_chars=self.anchor_max_anchor_chars,
                ),
            )
        middleware.extend([
                ToolCallLimitMiddleware(
                    tool_name="generate_quiz_paper",
                    run_limit=1,
                    exit_behavior="continue",
                ),
                *([ToolCallLimitMiddleware(tool_name="search_web", run_limit=1, exit_behavior="continue")] if use_web_search else []),
            ])

        return create_deep_agent(
            model=self.model,
            tools=tools,
            system_prompt=_append_recall_blocks(self.system_prompt_provider.practice_prompt(use_web_search), recall),
            middleware=middleware,
            checkpointer=self.checkpointer,
        )

    async def _recall(self, session_id: str, question: str, document_ids: list[str]) -> RecallContext | None:
        if self.memory_recall is None:
            return None
        try:
            subject = self.subject_resolver(document_ids) if self.subject_resolver else None
            return await self.memory_recall.recall(session_id, question, activity="practice", subject=subject)
        except Exception:  # noqa: BLE001 - memory remains a non-blocking side path
            logger.exception("Practice memory recall failed: session=%s", session_id)
            return None
