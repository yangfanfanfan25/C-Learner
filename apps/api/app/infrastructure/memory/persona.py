"""L3 画像生成器：deepagents agent 写 persona.md + 后处理。"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from pathlib import Path

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.messages import HumanMessage

from app.infrastructure.memory.scene_store import SceneBlockStore
from app.infrastructure.prompts.memory_prompts import MemoryPromptProvider
from app.schemas.memory import Persona

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 180
PERSONA_FILENAME = "persona.md"


def escape_xml_tags(text: str) -> str:
    """转义 < > &，防止画像正文破坏 <user-persona> 标签注入。"""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def strip_navigation(text: str) -> str:
    """剥掉 <scene-navigation> 尾段（LLM 可能误加，或旧导航）。"""
    return re.sub(
        r"\s*<scene-navigation>.*?</scene-navigation>\s*$",
        "",
        text,
        flags=re.DOTALL,
    )


def reattach_navigation(text: str, navigation: str) -> str:
    """把最新场景导航尾段重挂到正文末尾。"""
    return f"{text.strip()}\n\n<scene-navigation>\n{navigation}\n</scene-navigation>"


class LangChainPersonaGenerator:
    """L3 画像生成：LLM 当作会写文件的 Agent，在 persona 沙箱内写 persona.md。"""

    def __init__(
        self,
        model,
        scene_store: SceneBlockStore,
        persona_dir: str,
        prompt_provider: MemoryPromptProvider | None = None,
        timeout_seconds: int = _TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._scene_store = scene_store
        self._persona_dir = Path(persona_dir)
        self._prompt_provider = prompt_provider or MemoryPromptProvider()
        self._timeout = timeout_seconds

    async def generate(self, session_id: str, changed_scenes: list[str]) -> Persona:
        """增量/首次生成画像；无变化且已有 persona → 返回现有。"""
        from app.infrastructure.memory.files import LocalMemoryFileStorage

        fs = LocalMemoryFileStorage(self._persona_dir)
        existing = fs.read(PERSONA_FILENAME)
        mode = "incremental" if existing else "first"
        summaries = self._summaries(changed_scenes)
        if not summaries and existing:
            # 无变化且画像存在 → 跳过（返回现有画像）
            content, updated = self._parse_persona(existing)
            return Persona(content=content, updated_at_ms=updated)

        prompt = self._prompt_provider.l3_persona_prompt().format(
            mode=mode, summaries=summaries or "（无场景）"
        )
        backend = FilesystemBackend(root_dir=self._persona_dir, virtual_mode=True)
        agent = create_deep_agent(model=self._model, backend=backend, system_prompt=prompt)
        try:
            await asyncio.wait_for(
                agent.ainvoke({"messages": [HumanMessage(content="请生成用户画像")]}),
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - 生成失败不阻断，回退现有/空画像
            logger.warning("L3 画像生成失败: %s", exc)
            if existing:
                content, updated = self._parse_persona(existing)
                return Persona(content=content, updated_at_ms=updated)
            return Persona(content="", updated_at_ms=0)

        # 后处理：读 LLM 写的 persona.md → 剥导航 → escape → 重挂导航
        raw = fs.read(PERSONA_FILENAME) or ""
        body = escape_xml_tags(strip_navigation(raw).strip())
        navigation = self._navigation()
        final = reattach_navigation(body, navigation)
        fs.write(PERSONA_FILENAME, final)
        return Persona(content=body, updated_at_ms=int(time.time() * 1000))

    def _summaries(self, changed_scenes: list[str]) -> str:
        lines = []
        for meta in self._scene_store.list_blocks():
            if changed_scenes and meta.filename not in changed_scenes:
                continue
            lines.append(f"- {meta.filename}: {meta.summary}")
        return "\n".join(lines)

    def _navigation(self) -> str:
        return "\n".join(
            f"- {m.filename}: {m.summary}" for m in self._scene_store.list_blocks()
        )

    @staticmethod
    def _parse_persona(raw: str) -> tuple[str, int]:
        body = strip_navigation(raw).strip()
        return body, int(time.time() * 1000)
