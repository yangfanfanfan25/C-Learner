"""L1 召回注入：hybrid（向量+FTS5）+ RRF + 阈值 + 预算裁剪。"""

from __future__ import annotations

import logging

from app.infrastructure.memory.sanitize import sanitize_text
from app.schemas.memory import MemoryActivity, MemoryAtom, RecallContext

logger = logging.getLogger(__name__)


def rrf(ranked_ids: list[list[str]], k: int = 60) -> dict[str, float]:
    """Reciprocal Rank Fusion：对多个 ranked id 列表做 rank 融合。"""
    scores: dict[str, float] = {}
    for ranked in ranked_ids:
        for rank, id_ in enumerate(ranked):
            scores[id_] = scores.get(id_, 0.0) + 1.0 / (k + rank + 1)
    return scores


def budget_trim(
    memories: list[MemoryAtom],
    max_results: int,
    max_chars_per_memory: int,
    max_total_chars: int,
) -> tuple[list[MemoryAtom], bool]:
    """按条数/单条字数/总字数裁剪；超了丢后面，返回 (kept, truncated)。"""
    kept: list[MemoryAtom] = []
    total = 0
    truncated = False
    for atom in memories[:max_results]:
        content = atom.content[:max_chars_per_memory]
        if total + len(content) > max_total_chars:
            truncated = True
            break
        kept.append(atom.model_copy(update={"content": content}))
        total += len(content)
    return kept, truncated


class MemoryRecallService:
    """每轮读取 L3 persona，并仅在领域场景下召回满足阈值的 L1 记忆。"""

    def __init__(
        self,
        atom_repo,
        vector_store,
        embedding,
        file_storage,
        scene_store=None,
        score_threshold: float = 0.5,
        max_results: int = 5,
        max_chars_per_memory: int = 500,
        max_total_chars: int = 1500,
    ) -> None:
        self._atom_repo = atom_repo
        self._vector_store = vector_store
        self._embedding = embedding
        self._scene_store = scene_store
        self._file_storage = file_storage
        self._score_threshold = max(0.5, score_threshold)
        self._max_results = max_results
        self._max_chars_per_memory = max_chars_per_memory
        self._max_total_chars = max_total_chars

    async def recall(
        self,
        session_id: str,
        query: str,
        *,
        activity: str = "conversation",
        subject: str | None = None,
    ) -> RecallContext:
        persona = self._load_persona()
        try:
            activity_value = MemoryActivity(activity)
        except ValueError:
            activity_value = MemoryActivity.conversation
        strategies = self._strategies(activity_value, subject)
        if activity_value is MemoryActivity.conversation:
            return RecallContext(persona=persona)
        cleaned = sanitize_text(query)
        if len(cleaned) < 2:
            return RecallContext(persona=persona, relevant_strategies=strategies)

        memories = await self._hybrid_recall(cleaned, activity_value, subject)
        return RecallContext(persona=persona, relevant_strategies=strategies, relevant_memories=memories)

    async def _hybrid_recall(self, query: str, activity: MemoryActivity, subject: str | None) -> list[MemoryAtom]:
        qv = self._embedding.embed_query(query)
        vector_hits = self._vector_store.search(qv, top_k=self._max_results * 2)
        # 向量：COSINE 阈值过滤
        vector_ids = [h.id for h in vector_hits if h.score >= self._score_threshold]
        if not vector_ids:
            return []

        fts_ids: list[str] = []
        if len(query) >= 3:  # trigram 下限，短查询退化仅向量
            fts_hits = self._atom_repo.search_atoms_fts(query, top_k=self._max_results)
            eligible_ids = set(vector_ids)
            fts_ids = [
                h.columns.get("memory_id", "")
                for h in fts_hits
                if h.columns.get("memory_id", "") in eligible_ids
            ]

        scores = rrf([vector_ids, fts_ids], k=60)
        ranked = sorted(scores, key=scores.get, reverse=True)
        atoms = [a for a in self._atom_repo.get_atoms_by_ids(ranked)
                 if a.activity is activity and (not subject or not a.subject or a.subject == subject)]
        kept, _truncated = budget_trim(
            atoms, self._max_results, self._max_chars_per_memory, self._max_total_chars
        )
        return kept

    def _strategies(self, activity: MemoryActivity, subject: str | None) -> list[str]:
        if self._scene_store is None:
            return []
        return [m.summary for m in self._scene_store.list_blocks()
                if m.activity in (None, activity)
                and (not subject or not m.subject or m.subject == subject)
                and m.confidence >= 0.5 and m.evidence_count >= 2]

    def _load_persona(self) -> str | None:
        raw = self._file_storage.read("persona.md")
        if raw is None:
            return None
        # 剥掉导航尾段，返回正文
        import re
        return re.sub(r"\s*<scene-navigation>.*?</scene-navigation>\s*$", "", raw, flags=re.DOTALL).strip() or None
