"""会话锚点记忆中间件（AnchorMemoryMiddleware）。

与 ``SummarizationMiddleware`` 正交的短期记忆层：压缩是在上下文很长时对**全部**旧内容
做有损概括；锚点则在同一次模型调用前从原始消息增量独立提取少数关键信息（实体关系 + 背景设定），
作为下一次请求的事实补充注入 system，使早期关键事实在长对话/多次压缩后仍可被引用。

行为契约（与生产装配一一对应，供评测引擎与单测直接驱动）：
- 状态：``state["_anchor_text"]``（当前锚点正文）、``state["_anchor_consumed"]``
  （已提取到的原始消息条数，用于计算"本轮起新增内容"）。
- 触发：距上次提取新增 ≥ ``every_n_turns`` 轮（按消息对估算），或新增内容
  token ≥ ``min_new_tokens``；满足其一即触发一次提取。提取后 ``_anchor_consumed``
  推进到当前消息条数，因此不会在下一轮重复提取。
- 提取：把「已有锚点 + 增量消息」交给模型合并成新的纯文本锚点正文（单次 LLM 调用），
  裁剪到 ``max_anchor_chars``；失败时**保留旧锚点、不推进 consumed**（下轮可重试）。
- 注入：锚点非空时，每次模型请求都把它作为 ``<conversation-anchors>`` 段追加进
  system message（system 不参与 Summarization 的消息分区，锚点因此永不被压缩掉）。

依赖全部经构造函数注入（LLM 模型 + 提取提示词文本）；不 import 任何第三方具体库，
不内嵌提示词常量（默认取 ``chat_prompts.ANCHOR_EXTRACTION_PROMPT``）。
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Callable, NotRequired

from langchain.agents.middleware.types import (
    AgentMiddleware,
    AgentState,
    ExtendedModelResponse,
    ModelRequest,
    ModelResponse,
    PrivateStateAttr,
)
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langchain_core.messages.utils import count_tokens_approximately
from langgraph.types import Command
from pydantic import ValidationError

from app.schemas.memory import AnchorExtractionResult, AnchorFact
from app.infrastructure.prompts.chat_prompts import (
    ANCHOR_EXTRACTION_PROMPT,
    ANCHOR_INJECT_GUIDE,
    ANCHOR_TAG_CLOSE,
    ANCHOR_TAG_OPEN,
)

logger = logging.getLogger(__name__)

_STATE_TEXT = "_anchor_text"
_STATE_CONSUMED = "_anchor_consumed"
_STATE_FACTS = "_anchor_facts"
_STATE_READ_ONLY = "_anchor_read_only"


class AnchorState(AgentState):
    """锚点中间件私有状态：锚点正文 + 已消费消息计数。"""

    _anchor_text: Annotated[NotRequired[str], PrivateStateAttr]
    _anchor_consumed: Annotated[NotRequired[int], PrivateStateAttr]
    _anchor_facts: Annotated[NotRequired[list[dict[str, Any]]], PrivateStateAttr]


class AnchorMemoryMiddleware(AgentMiddleware[AnchorState]):
    """周期性提取「实体关系/背景设定」锚点并在压缩外持续注入的中间件。"""

    state_schema = AnchorState
    serialized_name: "str" = "AnchorMemoryMiddleware"

    def __init__(
        self,
        model: Any,
        *,
        extract_prompt: str | None = None,
        every_n_turns: int = 10,
        min_new_tokens: int = 2000,
        max_anchor_chars: int = 2000,
    ) -> None:
        """初始化。

        Args:
            model: 用于锚点提取的 LLM（真实调用，仅在触发时）。
            extract_prompt: 提取提示词模板（含 {existing_anchors}/{messages} 占位符）。
            every_n_turns: 距上次提取新增多少轮（消息对）即触发一次。
            min_new_tokens: 距上次提取新增内容达到该 token 数即触发。
            max_anchor_chars: 锚点正文最大字符数，超出按行裁剪。
        """
        self._model = model
        self._extract_prompt = extract_prompt or ANCHOR_EXTRACTION_PROMPT
        self._every_n_turns = every_n_turns
        self._min_new_tokens = min_new_tokens
        self._max_anchor_chars = max_anchor_chars
        # 评测/可观测计数（不入图状态）
        self.extract_calls: int = 0
        self.extract_input_tokens: int = 0
        # 调试/评测审计记录：保留实际 prompt 与模型输出，便于定位事实漏提或混写。
        self.extract_traces: list[dict[str, Any]] = []

    # -- 状态读写 -----------------------------------------------------------
    @staticmethod
    def _text(state: dict[str, Any] | None) -> str:
        value = (state or {}).get(_STATE_TEXT)
        return value if isinstance(value, str) else ""

    @staticmethod
    def _consumed(state: dict[str, Any] | None) -> int:
        value = (state or {}).get(_STATE_CONSUMED)
        return value if isinstance(value, int) else 0

    @staticmethod
    def _facts(state: dict[str, Any] | None) -> list[AnchorFact]:
        value = (state or {}).get(_STATE_FACTS)
        if not isinstance(value, list):
            return []
        facts: list[AnchorFact] = []
        for item in value:
            try:
                facts.append(AnchorFact.model_validate(item))
            except ValidationError:
                continue
        return facts

    @staticmethod
    def _is_summary_message(message: AnyMessage) -> bool:
        """压缩 middleware 产生的 summary 不属于锚点原始消息源。"""
        return (
            message.type == "human"
            and isinstance(getattr(message, "additional_kwargs", None), dict)
            and message.additional_kwargs.get("lc_source") == "summarization"
        )

    @classmethod
    def _raw_messages(cls, messages: list[AnyMessage]) -> list[AnyMessage]:
        """移除压缩 summary，保持锚点消费水位对齐原始消息序列。"""
        return [message for message in messages if not cls._is_summary_message(message)]

    # -- 触发判定 -----------------------------------------------------------
    def _should_extract(self, state: dict[str, Any] | None, messages: list[AnyMessage]) -> bool:
        consumed = self._consumed(state)
        delta = messages[consumed:]
        if not delta:
            return False
        # Count user turns rather than message pairs.  Middleware runs before
        # the current turn's AI response is appended, and tool/system messages
        # may also be present, so len(delta) // 2 drifts from the configured
        # cadence after the first extraction.
        new_rounds = sum(1 for message in delta if message.type == "human")
        new_tokens = count_tokens_approximately(delta)
        return new_rounds >= self._every_n_turns or new_tokens >= self._min_new_tokens

    # -- 提取 ---------------------------------------------------------------
    def _format_messages(self, delta: list[AnyMessage]) -> str:
        lines = []
        for msg in delta:
            role = "assistant" if msg.type == "ai" else ("human" if msg.type == "human" else msg.type)
            lines.append(f"[{role}] {_content_text(msg.content)}")
        return "\n".join(lines)

    @staticmethod
    def _clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        lines = text.splitlines()
        kept: list[str] = []
        total = 0
        for line in lines:
            if total + len(line) > limit and kept:
                break
            kept.append(line)
            total += len(line) + 1
        return "\n".join(kept).rstrip() + "…"

    @staticmethod
    def _merge_facts(existing: list[AnchorFact], incoming: list[AnchorFact]) -> list[AnchorFact]:
        merged = {(fact.subject.strip(), fact.attribute.strip()): fact for fact in existing}
        for fact in incoming:
            merged[(fact.subject.strip(), fact.attribute.strip())] = fact
        return list(merged.values())

    @staticmethod
    def _render_facts(facts: list[AnchorFact]) -> str:
        lines = []
        for fact in facts:
            time_prefix = f"{fact.time} " if fact.time else ""
            lines.append(f"{fact.subject}｜{fact.attribute}｜{time_prefix}{fact.value}")
        return "\n".join(lines)

    @staticmethod
    def _parse_facts(text: str) -> list[AnchorFact] | None:
        candidate = text.strip()
        if candidate.startswith("```"):
            candidate = candidate.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            return AnchorExtractionResult.model_validate(json.loads(candidate)).facts
        except (json.JSONDecodeError, ValidationError, TypeError):
            return None

    def _normalize_output(
        self,
        raw_output: str,
        existing_text: str,
        existing_facts: list[AnchorFact],
    ) -> tuple[str, list[dict[str, Any]] | None]:
        incoming = self._parse_facts(raw_output)
        if incoming is None:
            return self._clip(raw_output, self._max_anchor_chars), None
        merged = self._merge_facts(existing_facts, incoming)
        rendered = self._clip(self._render_facts(merged), self._max_anchor_chars)
        return rendered or existing_text, [fact.model_dump(mode="json") for fact in merged]

    def _extract_sync(
        self,
        existing: str,
        existing_facts: list[AnchorFact],
        messages: list[AnyMessage],
    ) -> tuple[str, list[dict[str, Any]] | None] | None:
        prompt = self._build_prompt(existing, messages)
        input_tokens = count_tokens_approximately([HumanMessage(content=prompt)])
        try:
            response = self._model.invoke(prompt)
            raw_output = _message_text(response).strip() or ""
            output, facts = self._normalize_output(raw_output, existing, existing_facts)
            self.extract_traces.append({"prompt": prompt, "input_tokens": input_tokens, "output": output, "raw_output": raw_output, "error": None})
            return output, facts
        except Exception as exc:  # noqa: BLE001 - 提取失败保留旧锚点
            self.extract_traces.append({"prompt": prompt, "input_tokens": input_tokens, "output": None, "error": f"{type(exc).__name__}: {exc}"})
            logger.warning("锚点提取失败，保留旧锚点: %s: %s", type(exc).__name__, exc)
            return None

    async def _extract(
        self,
        existing: str,
        existing_facts: list[AnchorFact],
        messages: list[AnyMessage],
    ) -> tuple[str, list[dict[str, Any]] | None] | None:
        prompt = self._build_prompt(existing, messages)
        self.extract_calls += 1
        input_tokens = count_tokens_approximately([HumanMessage(content=prompt)])
        self.extract_input_tokens += input_tokens
        try:
            response = await self._model.ainvoke(prompt)
            raw_output = _message_text(response).strip() or ""
            output, facts = self._normalize_output(raw_output, existing, existing_facts)
            self.extract_traces.append({"prompt": prompt, "input_tokens": input_tokens, "output": output, "raw_output": raw_output, "error": None})
            return output, facts
        except Exception as exc:  # noqa: BLE001 - 提取失败保留旧锚点
            self.extract_traces.append({"prompt": prompt, "input_tokens": input_tokens, "output": None, "error": f"{type(exc).__name__}: {exc}"})
            logger.warning("锚点提取失败，保留旧锚点: %s: %s", type(exc).__name__, exc)
            return None

    def _build_prompt(self, existing: str, messages: list[AnyMessage]) -> str:
        # 用占位符替换而非 str.format，避免对话正文里的花括号被误当模板字段。
        return (
            self._extract_prompt
            .replace("{existing_anchors}", existing.strip() or "（暂无）")
            .replace("{messages}", self._format_messages(messages))
            .replace("{max_chars}", str(self._max_anchor_chars))
        )

    # -- 注入 ---------------------------------------------------------------
    @staticmethod
    def _with_anchor_block(system_message: SystemMessage | None, text: str) -> SystemMessage:
        block = (
            f"\n\n{ANCHOR_TAG_OPEN}\n{ANCHOR_INJECT_GUIDE}\n{text}\n{ANCHOR_TAG_CLOSE}"
        )
        if system_message is None:
            return SystemMessage(content=block.lstrip())
        content = system_message.content
        if isinstance(content, str):
            return SystemMessage(content=content + block)
        # content block 列表（如多模态 system）：追加一个文本块
        blocks = list(content) if isinstance(content, list) else []
        blocks.append({"type": "text", "text": block})
        return SystemMessage(content=blocks)

    # -- 调用包装 -----------------------------------------------------------
    @staticmethod
    def _pack_update(inner: ModelResponse | ExtendedModelResponse, anchor_upd: dict[str, Any] | None):
        """合并锚点 state 更新与内层（summarization）返回，保证外层的 command 不丢。"""
        if not anchor_upd:
            return inner
        if isinstance(inner, ExtendedModelResponse):
            inner_upd = inner.command.update if inner.command else {}
            merged = {**inner_upd, **anchor_upd}
            return ExtendedModelResponse(
                model_response=inner.model_response,
                command=Command(update=merged),
            )
        return ExtendedModelResponse(model_response=inner, command=Command(update=anchor_upd))

    def _prepare(self, request: ModelRequest) -> tuple[ModelRequest, dict[str, Any] | None]:
        """同步前置：基于原始消息独立触发提取，并注入本次可用锚点。"""
        state = request.state if isinstance(request.state, dict) else {}
        messages = self._raw_messages(list(request.messages or []))
        existing = self._text(state)
        existing_facts = self._facts(state)
        anchor_upd: dict[str, Any] | None = None
        if not state.get(_STATE_READ_ONLY) and self._should_extract(state, messages):
            extracted = self._extract_sync(existing, existing_facts, messages[self._consumed(state):])
            if extracted is not None:
                new_text, facts = extracted
                anchor_upd = {
                    _STATE_TEXT: new_text,
                    _STATE_CONSUMED: len(messages),
                }
                if facts is not None:
                    anchor_upd[_STATE_FACTS] = facts
        # 本轮新提取结果只写入 state，下一次请求才注入；避免当前请求同时
        # 消费尚未与压缩分支完成协调的新记忆。
        if existing:
            new_system = self._with_anchor_block(request.system_message, existing)
            if new_system is not request.system_message:
                request = request.override(system_message=new_system)
        return request, anchor_upd

    async def _aprepare(self, request: ModelRequest) -> tuple[ModelRequest, dict[str, Any] | None]:
        """异步前置：基于原始消息独立触发提取，并注入本次可用锚点。"""
        state = request.state if isinstance(request.state, dict) else {}
        messages = self._raw_messages(list(request.messages or []))
        existing = self._text(state)
        existing_facts = self._facts(state)
        anchor_upd: dict[str, Any] | None = None
        if not state.get(_STATE_READ_ONLY) and self._should_extract(state, messages):
            extracted = await self._extract(existing, existing_facts, messages[self._consumed(state):])
            if extracted is not None:
                new_text, facts = extracted
                anchor_upd = {
                    _STATE_TEXT: new_text,
                    _STATE_CONSUMED: len(messages),
                }
                if facts is not None:
                    anchor_upd[_STATE_FACTS] = facts
        if existing:
            new_system = self._with_anchor_block(request.system_message, existing)
            if new_system is not request.system_message:
                request = request.override(system_message=new_system)
        return request, anchor_upd

    def wrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse | ExtendedModelResponse:
        req, upd = self._prepare(request)
        inner = handler(req)
        return self._pack_update(inner, upd)

    async def awrap_model_call(
        self,
        request: ModelRequest,
        handler: Callable[[ModelRequest], Any],
    ) -> Any:
        req, upd = await self._aprepare(request)
        inner = await handler(req)
        return self._pack_update(inner, upd)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            str(item.get("text") or item.get("content") or "") if isinstance(item, dict) else str(item)
            for item in content
        )
    return str(content)


def _message_text(response: Any) -> str:
    """把模型响应（AIMessage / str / dict）归一为文本。"""
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if content is None:
        return str(response)
    return _content_text(content)
