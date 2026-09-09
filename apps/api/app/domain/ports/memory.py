"""长期记忆端口（Phase 1：仅 L0 捕获；Phase 2 增补 L1）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from app.schemas.memory import (
    DedupDecision,
    L0Message,
    L0Context,
    L1ExtractionResult,
    MemoryAtom,
    Persona,
    RecallContext,
    SceneExtractOutcome,
)

if TYPE_CHECKING:
    from app.infrastructure.memory.fts import FtsHit
    from app.infrastructure.memory.models import MemoryGenerationLog


class MemoryVectorWriter(Protocol):
    def insert(self, rows: list[dict[str, object]]) -> int: ...


class MemoryCapturePort(Protocol):
    """L0 会话捕获端口（消费者 = ChatService）。

    ChatService 每轮对话完成后调用，把一条 user/assistant 消息清洗后写入
    L0 四路存储。实现失败不得向上抛出阻断对话（捕获是旁路）。
    """

    def capture_message(
        self,
        session_id: str,
        role: str,
        content: str,
        context: L0Context | None = None,
    ) -> None:
        """清洗并落库一条消息。"""
        ...


class MemoryAtomRepository(Protocol):
    """L1 记忆原子的 SQLite 持久化端口（消费者 = L1 runner）。"""

    def append_atom(self, atom: MemoryAtom) -> None: ...
    def list_atoms_since(self, updated_after_ms: int, limit: int) -> list[MemoryAtom]: ...
    def delete_atoms(self, ids: list[str]) -> None: ...
    def search_atoms_fts(self, query: str, top_k: int) -> list[FtsHit]: ...


class AtomExtractor(Protocol):
    """L1 记忆提取端口（消费者 = L1 runner）。"""

    async def extract(self, messages: list[L0Message]) -> L1ExtractionResult: ...


class DedupJudge(Protocol):
    """L1 去重判定端口（消费者 = L1 runner）。"""

    async def judge(
        self, new_atoms: list[MemoryAtom], candidates: list[MemoryAtom]
    ) -> list[DedupDecision]: ...


class MemoryGenerationLogRepository(Protocol):
    """生成日志端口（消费者 = L1 runner）。"""

    def append(self, log: MemoryGenerationLog) -> None: ...


class SceneExtractorPort(Protocol):
    """L2 场景抽取端口（消费者 = L2 runner）。"""

    async def extract(self, session_id: str, new_memories: list[MemoryAtom]) -> SceneExtractOutcome: ...


class PersonaGeneratorPort(Protocol):
    """L3 画像生成端口（消费者 = L3 runner）。"""

    async def generate(self, session_id: str, changed_scenes: list[str]) -> Persona: ...


class MemoryRecallPort(Protocol):
    """召回注入端口（消费者 = DeepAgentsChatWorkflowRunner）。"""

    async def recall(
        self,
        session_id: str,
        query: str,
        *,
        activity: str = "conversation",
        subject: str | None = None,
    ) -> RecallContext: ...
