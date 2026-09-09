"""L2 场景抽取器：deepagents agent + FilesystemBackend 虚拟文件沙箱。"""

from __future__ import annotations

import asyncio
import logging

from deepagents import create_deep_agent
from deepagents.backends.filesystem import FilesystemBackend
from langchain_core.messages import HumanMessage

from app.infrastructure.memory.scene_postprocess import ScenePostProcessor
from app.infrastructure.memory.scene_store import SceneBlockStore
from app.infrastructure.prompts.memory_prompts import MemoryPromptProvider
from app.schemas.memory import MemoryAtom, SceneExtractOutcome

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 300


class LangChainSceneExtractor:
    """L2 场景抽取：LLM 当作会改文件的 Agent，在 scene_blocks 沙箱内维护场景块。"""

    def __init__(
        self,
        model,
        scene_store: SceneBlockStore,
        scene_blocks_dir: str,
        prompt_provider: MemoryPromptProvider | None = None,
        max_scenes: int = 15,
        timeout_seconds: int = _TIMEOUT_SECONDS,
    ) -> None:
        self._model = model
        self._scene_store = scene_store
        self._scene_blocks_dir = scene_blocks_dir
        self._prompt_provider = prompt_provider or MemoryPromptProvider()
        self._max_scenes = max_scenes
        self._timeout = timeout_seconds

    async def extract(
        self, session_id: str, new_memories: list[MemoryAtom]
    ) -> SceneExtractOutcome:
        """让 LLM agent 在沙箱内维护场景块；返回变更结果。"""
        if not new_memories:
            return SceneExtractOutcome()
        before = self._snapshot()  # 变更检测基线
        prompt = self._build_prompt(new_memories)
        backend = FilesystemBackend(root_dir=self._scene_blocks_dir, virtual_mode=True)
        agent = create_deep_agent(
            model=self._model,
            backend=backend,
            system_prompt=prompt,
        )
        try:
            await asyncio.wait_for(
                agent.ainvoke({"messages": [HumanMessage(content=self._memories_text(new_memories))]}),
                timeout=self._timeout,
            )
        except Exception as exc:  # noqa: BLE001 - agent 失败不阻断，返回空结果
            logger.warning("L2 场景抽取失败: %s", exc)
            return SceneExtractOutcome()
        # 后处理：软删清理、空文件删除、文件名规范化，再重建索引
        post = ScenePostProcessor(self._scene_store)
        post.cleanup()
        post.normalize_filenames()
        self._scene_store.sync_index()
        changed = self._diff(before)
        return SceneExtractOutcome(changed_scenes=changed)

    def _build_prompt(self, new_memories: list[MemoryAtom]) -> str:
        summaries = "\n".join(
            f"- {m.filename}: {m.summary}" for m in self._scene_store.list_blocks()
        ) or "（无现有场景）"
        capacity_warning = ""
        n = len(self._scene_store.list_blocks())
        if n >= self._max_scenes:
            capacity_warning = (
                f"警告：场景块已达上限 {self._max_scenes}，必须合并 2-4 个最相似场景，"
                "禁止新建。"
            )
        elif n == self._max_scenes - 1:
            capacity_warning = (
                f"警告：场景块接近上限（{n}/{self._max_scenes}），只能更新已有块，禁止新建。"
            )
        return self._prompt_provider.l2_scene_prompt().format(
            capacity_warning=capacity_warning,
            summaries=summaries,
            memories=self._memories_text(new_memories),
        )

    def _snapshot(self) -> set[str]:
        return {m.filename for m in self._scene_store.list_blocks()}

    def _diff(self, before: set[str]) -> list[str]:
        after = {m.filename for m in self._scene_store.list_blocks()}
        return sorted((before - after) | (after - before))

    @staticmethod
    def _memories_text(memories: list[MemoryAtom]) -> str:
        return "\n".join(
            f"- id={m.id} activity={m.activity.value} subject={m.subject or 'unknown'} "
            f"[{m.type.value}] {m.content} evidence={','.join(m.source_message_ids)}"
            for m in memories
        )
