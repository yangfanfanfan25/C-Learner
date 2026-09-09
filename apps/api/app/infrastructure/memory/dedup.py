"""L1 记忆去重判定器：LLM → list[DedupDecision]，解析失败 fallback_store_all。"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from app.infrastructure.prompts.memory_prompts import MemoryPromptProvider
from app.schemas.memory import DedupAction, DedupDecision, MemoryAtom

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 180


def _message_text(response: Any) -> str:
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


def _extract_json_array(text: str) -> list:
    """剥 markdown 围栏，取首个 [ 到末尾 ]，json.loads。"""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    start = stripped.find("[")
    end = stripped.rfind("]")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("模型输出中未找到 JSON 数组")
    return json.loads(stripped[start : end + 1])


class LangChainDedupJudge:
    """L1 去重判定：拼 prompt → ainvoke → 解析 JSON 数组 → 关联新原子。"""

    def __init__(
        self,
        model: Any,
        prompt_provider: MemoryPromptProvider | None = None,
        timeout_seconds: int = _TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._prompt_provider = prompt_provider or MemoryPromptProvider()
        self._timeout = timeout_seconds

    async def judge(
        self, new_atoms: list[MemoryAtom], candidates: list[MemoryAtom]
    ) -> list[DedupDecision]:
        """逐条判定新记忆；空输入返回空。解析失败降级为全 store（宁可重复不丢）。"""
        if not new_atoms:
            return []
        prompt = self._prompt_provider.l1_dedup_prompt().format(
            new_atoms=self._format_atoms(new_atoms),
            candidates=self._format_atoms(candidates),
        )
        try:
            response = await asyncio.wait_for(
                self._model.ainvoke(prompt), timeout=self._timeout
            )
            raw_list = _extract_json_array(_message_text(response))
            decisions: list[DedupDecision] = []
            for i, atom in enumerate(new_atoms):
                raw = raw_list[i] if i < len(raw_list) and isinstance(raw_list[i], dict) else {}
                decisions.append(self._to_decision(atom, raw))
            return decisions
        except Exception as exc:  # noqa: BLE001 - 解析失败降级为全 store
            logger.warning("L1 去重判定失败，降级为全 store: %s: %s", type(exc).__name__, exc)
            return self._fallback_store_all(new_atoms)

    def _to_decision(self, atom: MemoryAtom, raw: dict) -> DedupDecision:
        try:
            action = DedupAction(raw.get("action", "store"))
        except ValueError:
            action = DedupAction.store
        merged_priority = raw.get("merged_priority")
        return DedupDecision(
            action=action,
            memory=atom,
            target_ids=self._as_str_list(raw.get("target_ids")),
            merged_content=raw.get("merged_content") if isinstance(raw.get("merged_content"), str) else None,
            merged_priority=merged_priority if isinstance(merged_priority, int) else None,
            merged_timestamps=self._as_int_list(raw.get("merged_timestamps")),
        )

    @staticmethod
    def _fallback_store_all(new_atoms: list[MemoryAtom]) -> list[DedupDecision]:
        return [DedupDecision(action=DedupAction.store, memory=atom) for atom in new_atoms]

    @staticmethod
    def _format_atoms(atoms: list[MemoryAtom]) -> str:
        return "\n".join(
            f"[{a.id}|{a.type.value}] {a.content}" for a in atoms
        )

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
