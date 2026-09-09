"""deepagents 智能体聊天工作流。

职责：用 ``create_deep_agent`` 组装一个由智能体判断执行 RAG 问答流程的
聊天运行器，替代旧的确定性 LangGraph 图流程。

与旧实现的关键差异：

- 不再硬编码 ``semantic_search -> [web_search] -> answer`` 的图边；
  知识库检索与联网搜索被封装为工具，由智能体自行判断何时调用。
- 智能体始终优先检索知识库；前端开启 ``enable_web_search`` 后同时提供
  联网搜索工具，由智能体汇总两方面结果综合回答。
- 保留 ``SummarizationMiddleware`` 会话压缩机制：``trigger=("tokens", 50000)`` /
  ``keep=("messages", 8)``，仅在累计 token ≥ 50000 时压缩（减少频繁压缩）。
- 压缩摘要使用自定义 ``summary_prompt``（来自 ``SystemPromptProvider.summarization_prompt()``，
  文本唯一出处 ``app/infrastructure/prompts/chat_prompts.py``），显式禁止章节标题，
  防止默认摘要模板的 ``SESSION INTENT / SUMMARY`` 格式泄漏到回答。
- 会话记忆仍通过 ``AsyncSqliteSaver`` checkpointer + ``thread_id=session_id``
  持久化，压缩阈值按累计 token 数触发。
- 系统提示词不内嵌在本模块：通过构造函数注入 ``SystemPromptProvider`` 获取，
  提示词文本唯一出处为 ``app/infrastructure/prompts/chat_prompts.py``。

对外契约（``ChatWorkflowRunner``）与 SSE 事件类型保持不变。
"""

from __future__ import annotations

import logging
import json
from collections.abc import AsyncIterator
from typing import Any, Callable

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, ToolMessage
from langchain.agents.middleware import ToolCallLimitMiddleware

from deepagents import (
    GeneralPurposeSubagentProfile,
    HarnessProfile,
    create_deep_agent,
    register_harness_profile,
)
from deepagents.backends import StateBackend
from deepagents.middleware.summarization import SummarizationMiddleware

from app.domain.ports.chat_workflow import ChatWorkflowEvent
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.memory import MemoryRecallPort
from app.domain.ports.prompts import SystemPromptProvider
from app.domain.ports.semantic_store import SemanticVectorStore
from app.domain.ports.web_search import WebSearchProvider
from app.schemas.memory import RecallContext
from app.infrastructure.prompts.memory_prompts import (
    RELEVANT_MEMORIES_TAG,
    USER_PERSONA_TAG,
)
from app.infrastructure.deepagents.tools import (
    SourcesCollector,
    build_knowledge_search_tool,
    build_web_search_tool,
)

logger = logging.getLogger(__name__)

# 需要从 deepagents 内置工具集中移除的工具（本地 RAG 问答不需要文件系统/子智能体能力）。
_BUILTIN_TOOL_NAMES = frozenset(
    {
        "ls",
        "read_file",
        "write_file",
        "edit_file",
        "delete",
        "glob",
        "grep",
        "execute",
        "task",
    }
)

_registered_profile_keys: set[str] = set()
"""已注册 RAG HarnessProfile 的模型键，避免重复注册。"""


def _model_provider(model: BaseChatModel) -> str | None:
    try:
        params = model._get_ls_params()
    except Exception:  # noqa: BLE001 - 自定义模型可能不实现该接口
        return None
    if isinstance(params, dict):
        provider = params.get("ls_provider")
        if isinstance(provider, str) and provider:
            return provider
    return None


def _model_identifier(model: BaseChatModel) -> str | None:
    for attr in ("model_name", "model"):
        value = getattr(model, attr, None)
        if isinstance(value, str) and value:
            return value
    return None


def _ensure_rag_harness_profile(model: BaseChatModel) -> None:
    """为当前模型注册 HarnessProfile，移除内置文件系统/子智能体工具。

    deepagents 默认暴露 ``ls``/``read_file``/``write_file``/``execute``/``task``
    等内置工具；本地 RAG 问答只应暴露知识库与联网搜索工具，故按模型键注册一次
    profile 以隐藏这些内置工具并禁用默认 general-purpose 子智能体。
    """
    provider = _model_provider(model)
    identifier = _model_identifier(model)
    if not provider or not identifier:
        logger.debug(
            "无法解析模型 provider/identifier，跳过 RAG HarnessProfile 注册：%r/%r",
            provider,
            identifier,
        )
        return
    key = f"{provider}:{identifier}"
    if key in _registered_profile_keys:
        return
    register_harness_profile(
        key,
        HarnessProfile(
            excluded_tools=_BUILTIN_TOOL_NAMES,
            general_purpose_subagent=GeneralPurposeSubagentProfile(enabled=False),
        ),
    )
    _registered_profile_keys.add(key)


class DeepAgentsChatWorkflowRunner:
    """基于 deepagents 的智能体聊天运行器。

    依赖全部通过构造函数注入：模型、checkpointer、embedding、向量库、联网搜索。
    """

    def __init__(
        self,
        model: BaseChatModel,
        checkpointer: Any,
        embedding_provider: EmbeddingProvider,
        vector_store: SemanticVectorStore,
        web_search_provider: WebSearchProvider,
        system_prompt_provider: SystemPromptProvider,
        rag_top_k: int = 5,
        web_search_max_results: int = 5,
        memory_recall: MemoryRecallPort | None = None,
        subject_resolver: Callable[[list[str]], str | None] | None = None,
        *,
        anchor_memory: bool = True,
        anchor_every_n_turns: int = 10,
        anchor_min_new_tokens: int = 2000,
        anchor_max_anchor_chars: int = 2000,
        summarization_trigger_tokens: int = 50000,
        summarization_trigger_messages: int | None = None,
    ):
        self.model = model
        self.checkpointer = checkpointer
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.web_search_provider = web_search_provider
        self.system_prompt_provider = system_prompt_provider
        self.rag_top_k = rag_top_k
        self.web_search_max_results = web_search_max_results
        self.memory_recall = memory_recall
        self.subject_resolver = subject_resolver
        # 锚点记忆中间件（可选，默认关；经可选参数注入，既有调用方零破坏）
        self.anchor_memory = anchor_memory
        self.anchor_every_n_turns = anchor_every_n_turns
        self.anchor_min_new_tokens = anchor_min_new_tokens
        self.anchor_max_anchor_chars = anchor_max_anchor_chars
        self.summarization_trigger_tokens = summarization_trigger_tokens
        self.summarization_trigger_messages = summarization_trigger_messages
        _ensure_rag_harness_profile(model)

    async def stream_events(
        self,
        session_id: str,
        question: str,
        document_ids: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> AsyncIterator[ChatWorkflowEvent]:
        sources_collector = SourcesCollector()
        selected = set(capabilities or [])
        recall_context = await self._recall(
            session_id,
            question,
            activity=("practice" if "practice" in selected else "knowledge" if "knowledge" in selected else "conversation"),
            subject=self.subject_resolver(document_ids or []) if self.subject_resolver else None,
        )
        agent = self._build_agent(selected, recall_context)
        config = {"configurable": {"thread_id": session_id}}
        input_state = {"messages": [HumanMessage(content=_prepend_memories(question, recall_context))]}

        if "knowledge" in selected:
            yield ChatWorkflowEvent("status", "searching_knowledge")

        web_status_emitted = False
        generating_emitted = False
        active_tool_calls: dict[str, dict[str, Any]] = {}
        # 框架原生流式：messages=LLM token，tools=工具生命周期与输出，
        # custom=业务自定义来源事件。
        async for chunk in agent.astream(
            input_state,
            config=config,
            stream_mode=["messages", "tools", "custom"],
            version="v2",
        ):
            if chunk["type"] == "tools":
                payload = chunk["data"]
                step = tool_stream_step(payload, active_tool_calls)
                if step is None:
                    continue
                if step["kind"] == "tool_start" and step["tool"] == "search_web" and not web_status_emitted:
                    web_status_emitted = True
                    yield ChatWorkflowEvent("status", "searching_web")
                yield ChatWorkflowEvent("step", step)
                continue

            if chunk["type"] == "custom":
                payload = chunk["data"]
                kind = payload.get("kind")
                if kind == "sources":
                    # 来源为累积列表语义：合并去重后整表下发（保持与旧收集器一致）。
                    sources_collector.add(payload.get("data") or [])
                    new_sources = sources_collector.drain()
                    if new_sources:
                        yield ChatWorkflowEvent("sources", new_sources)
                continue

            # messages 模式：data 为 (message_chunk, metadata) 元组
            chunk, metadata = chunk["data"]
            node = metadata.get("langgraph_node") if isinstance(metadata, dict) else None

            # 工具结果消息不作为回答 token 输出。
            if node == "tools" or isinstance(chunk, ToolMessage):
                continue

            # 逐 token 输出回答内容。
            for token in content_tokens(getattr(chunk, "content", "")):
                if not generating_emitted:
                    generating_emitted = True
                    yield ChatWorkflowEvent("status", "generating")
                yield ChatWorkflowEvent("token", token)

        # 兜底：流结束后仍可能残留未回传的来源。
        trailing_sources = sources_collector.drain()
        if trailing_sources:
            yield ChatWorkflowEvent("sources", trailing_sources)

    async def _recall(
        self,
        session_id: str,
        question: str,
        *,
        activity: str,
        subject: str | None,
    ) -> RecallContext | None:
        """召回注入；失败/未配置返回 None（旁路不阻断对话）。"""
        if self.memory_recall is None:
            return None
        try:
            return await self.memory_recall.recall(
                session_id,
                question,
                activity=activity,
                subject=subject,
            )
        except Exception:  # noqa: BLE001
            logger.exception("召回注入失败: session=%s", session_id)
            return None

    def _build_agent(self, capabilities: set[str], recall_context: RecallContext | None = None):
        tools: list[Any] = []
        if "knowledge" in capabilities:
            tools.append(build_knowledge_search_tool(
                embedding_provider=self.embedding_provider,
                vector_store=self.vector_store,
                top_k=self.rag_top_k,
            ))
        if "web_search" in capabilities:
            tools.append(
                build_web_search_tool(
                    web_search_provider=self.web_search_provider,
                    max_results=self.web_search_max_results,
                )
            )

        summary_trigger: Any = ("tokens", self.summarization_trigger_tokens)
        if self.summarization_trigger_messages is not None:
            summary_trigger = [
                summary_trigger,
                ("messages", self.summarization_trigger_messages),
            ]
        summarization = SummarizationMiddleware(
            model=self.model,
            backend=StateBackend(),
            trigger=summary_trigger,
            keep=("messages", 8),
            summary_prompt=self.system_prompt_provider.summarization_prompt(),
        )
        middleware: list[Any] = [summarization]
        if self.anchor_memory:
            # 锚点在外层：先于压缩看到原始消息，保证在压缩前完成增量提取。
            from app.infrastructure.deepagents.anchor_memory import AnchorMemoryMiddleware

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
        if "knowledge" in capabilities:
            middleware.append(ToolCallLimitMiddleware(
                tool_name="search_knowledge", run_limit=1, exit_behavior="continue"
            ))
        if "web_search" in capabilities:
            middleware.append(
                ToolCallLimitMiddleware(
                    tool_name="search_web",
                    run_limit=1,
                    exit_behavior="continue",
                )
            )

        return create_deep_agent(
            model=self.model,
            tools=tools,
            system_prompt=_append_recall_blocks(
                self.system_prompt_provider.retrieval_prompt("web_search" in capabilities)
                if capabilities else self.system_prompt_provider.direct_prompt(),
                recall_context,
            ),
            middleware=middleware,
            checkpointer=self.checkpointer,
        )


def _append_recall_blocks(base: str, recall: RecallContext | None) -> str:
    """只把 L3 persona 追加为 system 稳定段；其它记忆层不得进入。"""
    if recall is None:
        return base
    prompt = base
    if recall.persona:
        prompt += f"\n\n{USER_PERSONA_TAG}\n{recall.persona}\n</{USER_PERSONA_TAG[1:]}"
    return prompt


def _prepend_memories(question: str, recall: RecallContext | None) -> str:
    """把 L2 策略和合格 L1 情境记忆作为本轮 user 上下文前缀。"""
    if recall is None or (not recall.relevant_memories and not recall.relevant_strategies):
        return question
    blocks = []
    if recall.relevant_strategies:
        blocks.append("<learning-strategies>\n" + "\n".join(f"- {s}" for s in recall.relevant_strategies) + "\n</learning-strategies>")
    if recall.relevant_memories:
        memories_text = "\n".join(f"- {m.content}" for m in recall.relevant_memories)
        blocks.append(f"{RELEVANT_MEMORIES_TAG}\n{memories_text}\n</{RELEVANT_MEMORIES_TAG[1:]}")
    return "\n\n".join(blocks) + "\n\n" + question


def content_tokens(content: object) -> list[str]:
    """把模型输出的 content（字符串或 content block 列表）拆成文本 token 序列。

    供检索与练习两个运行器共用；工具结果不作为回答 token 输出。
    """
    if isinstance(content, str):
        return [content] if content else []
    if isinstance(content, list):
        tokens: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") in {"text", "text_delta"}:
                text = item.get("text") or item.get("content") or ""
                if text:
                    tokens.append(str(text))
        return tokens
    return []


def tool_stream_step(
    payload: object,
    active_tool_calls: dict[str, dict[str, Any]],
) -> dict[str, Any] | None:
    """把 LangGraph 原生 tools 流归一为可由前端按调用 ID 更新的步骤。"""
    if not isinstance(payload, dict):
        return None
    event = payload.get("event")
    call_id = str(payload.get("tool_call_id") or "")
    if not call_id:
        return None

    if event == "tool-started":
        tool_name = str(payload.get("tool_name") or "unknown")
        args = payload.get("input")
        normalized_args = args if isinstance(args, dict) else None
        active_tool_calls[call_id] = {"tool": tool_name, "args": normalized_args}
        return {
            "id": call_id,
            "kind": "tool_start",
            "tool": tool_name,
            "message": _tool_start_message(tool_name, normalized_args),
            "args": normalized_args,
            "output": None,
        }

    call = active_tool_calls.pop(call_id, {})
    tool_name = str(call.get("tool") or "unknown")
    args = call.get("args")
    if event == "tool-finished":
        output = _tool_output_text(payload.get("output"))
        return {
            "id": call_id,
            "kind": "tool_result",
            "tool": tool_name,
            "message": f"{_tool_label(tool_name)}完成",
            "args": args,
            "output": output,
        }
    if event == "tool-error":
        error = str(payload.get("message") or "工具执行失败")
        return {
            "id": call_id,
            "kind": "tool_result",
            "tool": tool_name,
            "message": f"{_tool_label(tool_name)}失败",
            "args": args,
            "output": error,
        }
    return None


def _tool_label(tool_name: str) -> str:
    return {
        "search_knowledge": "检索本地知识库",
        "search_web": "联网搜索",
        "generate_quiz_paper": "生成练习题",
    }.get(tool_name, f"工具 {tool_name}")


def _tool_start_message(tool_name: str, args: dict[str, Any] | None) -> str:
    values = args or {}
    detail = values.get("query") or values.get("requirements")
    label = _tool_label(tool_name)
    return f"正在{label}：{detail}" if detail else f"正在{label}"


def _tool_output_text(output: object) -> str:
    if isinstance(output, ToolMessage):
        return _tool_output_text(output.content)
    if isinstance(output, str):
        return output
    content = getattr(output, "content", None)
    if content is not None:
        return _tool_output_text(content)
    if isinstance(output, (dict, list)):
        return json.dumps(output, ensure_ascii=False, indent=2, default=str)
    return str(output) if output is not None else ""
