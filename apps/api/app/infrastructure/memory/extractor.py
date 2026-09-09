"""L1 记忆提取器：LLM → JSON → L1ExtractionResult。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import uuid
from typing import Any

from app.infrastructure.prompts.memory_prompts import MemoryPromptProvider
from app.schemas.memory import L0Message, L1ExtractionResult, MemoryActivity, MemoryAtom, MemoryType

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 180
_MAX_RETRIES = 1


def _message_text(response: Any) -> str:
    """把 ainvoke 返回（AIMessage / str / dict）归一为文本。"""
    if isinstance(response, str):
        return response
    content = getattr(response, "content", None)
    if content is None:
        return str(response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(
            str(item.get("text") or item.get("content") or "")
            for item in content
            if isinstance(item, dict)
        )
    return str(content)


def _extract_json(text: str) -> dict:
    """剥 markdown 围栏，取首个 { 到末尾 }，json.loads。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("模型输出中未找到 JSON 对象")
    return json.loads(stripped[start : end + 1])


class LangChainAtomExtractor:
    """L1 记忆提取：拼 prompt → ainvoke → 解析 JSON → 填系统字段 → 校验。"""

    def __init__(
        self,
        model: Any,
        prompt_provider: MemoryPromptProvider | None = None,
        timeout_seconds: int = _TIMEOUT_SECONDS,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self._model = model
        self._prompt_provider = prompt_provider or MemoryPromptProvider()
        self._timeout = timeout_seconds
        self._max_retries = max_retries

    async def extract(self, messages: list[L0Message]) -> L1ExtractionResult:
        """从一组同会话消息提取记忆；空输入返回空结果。"""
        if not messages:
            return L1ExtractionResult(scene_name="", message_ids=[], memories=[])
        session_id = messages[0].session_id
        prompt = self._prompt_provider.l1_extraction_prompt().format(
            messages=self._format_messages(messages)
        )
        last_error: Exception | None = None
        for attempt in range(self._max_retries + 1):
            try:
                response = await asyncio.wait_for(
                    self._model.ainvoke(prompt), timeout=self._timeout
                )
                payload = _extract_json(_message_text(response))
                memories: list[MemoryAtom] = []
                for raw in self._as_list(payload.get("memories")):
                    atom = self._to_atom(raw, session_id)
                    if atom is not None:
                        memories.append(atom)
                return L1ExtractionResult(
                    scene_name=str(payload.get("scene_name", "")),
                    message_ids=self._as_str_list(payload.get("message_ids")),
                    memories=memories,
                )
            except Exception as exc:  # noqa: BLE001 - 调用/解析/转换失败统一重试
                last_error = exc
                logger.warning(
                    "L1 提取尝试 %d 失败: %s: %s", attempt + 1, type(exc).__name__, exc
                )
        raise RuntimeError(
            f"记忆提取失败：{type(last_error).__name__}: {last_error}"
        )

    def _to_atom(self, raw: Any, session_id: str) -> MemoryAtom | None:
        """防御式转换：空/null content 跳过；非法 type/priority/列表回退。"""
        if not isinstance(raw, dict):
            return None
        content = raw.get("content")
        if not isinstance(content, str) or not content.strip():
            return None
        try:
            type_ = MemoryType(raw.get("type", "episodic"))
        except ValueError:
            type_ = MemoryType.episodic
        try:
            activity = MemoryActivity(raw.get("activity", "conversation"))
        except ValueError:
            activity = MemoryActivity.conversation
        try:
            priority = int(raw.get("priority", 50))
        except (TypeError, ValueError):
            priority = 50
        now_ms = int(time.time() * 1000)
        return MemoryAtom(
            id=str(uuid.uuid4()),
            session_id=session_id,
            content=content,
            type=type_,
            priority=priority,
            source_message_ids=self._as_str_list(raw.get("source_message_ids")),
            scene_name=raw.get("scene_name") if isinstance(raw.get("scene_name"), str) else None,
            activity=activity,
            subject=raw.get("subject") if isinstance(raw.get("subject"), str) else None,
            scope=raw.get("scope") if raw.get("scope") in {"activity", "subject"} else "activity",
            metadata=raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
            timestamps=self._as_int_list(raw.get("timestamps")),
            version=1,
            created_at_ms=now_ms,
            updated_at_ms=now_ms,
        )

    @staticmethod
    def _as_list(value: Any) -> list:
        return value if isinstance(value, list) else []

    @staticmethod
    def _as_str_list(value: Any) -> list[str]:
        return [str(x) for x in value] if isinstance(value, list) else []

    @staticmethod
    def _as_int_list(value: Any) -> list[int]:
        if not isinstance(value, list):
            return []
        out: list[int] = []
        for x in value:
            try:
                out.append(int(x))
            except (TypeError, ValueError):
                pass
        return out

    @staticmethod
    def _format_messages(messages: list[L0Message]) -> str:
        return "\n".join(
            f"[{m.id}|{m.role}|context={m.context.model_dump_json()}] {m.content}"
            for m in messages
        )
