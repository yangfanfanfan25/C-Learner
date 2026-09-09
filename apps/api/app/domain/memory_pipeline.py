"""L1 记忆提取 runner：批窗口/游标/backlog/重分组/写编排。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.memory import (
    AtomExtractor,
    DedupJudge,
    MemoryAtomRepository,
    MemoryGenerationLogRepository,
)
from app.infrastructure.memory.journal import JsonlJournalStore
from app.infrastructure.memory.vector import MilvusMemoryVectorStore
from app.schemas.memory import (
    DedupAction,
    DedupDecision,
    L0Message,
    L1ExtractionResult,
    MemoryAtom,
)

logger = logging.getLogger(__name__)

RECORDS_CATEGORY = "records"


class L1Runner:
    """从 L0 增量消息提取 L1 记忆：批窗口 → 重分组 → 提取 → 去重 → 写。"""

    def __init__(
        self,
        l0_repo,
        atom_repo: MemoryAtomRepository,
        extractor: AtomExtractor,
        dedup_judge: DedupJudge,
        journal: JsonlJournalStore,
        vector_store: MilvusMemoryVectorStore | None = None,
        embedding: EmbeddingProvider | None = None,
        generation_log_repo: MemoryGenerationLogRepository | None = None,
        batch_query: int = 20,
        batch_process: int = 10,
    ) -> None:
        self._l0_repo = l0_repo
        self._atom_repo = atom_repo
        self._extractor = extractor
        self._dedup_judge = dedup_judge
        self._journal = journal
        self._vector_store = vector_store
        self._embedding = embedding
        self._generation_log_repo = generation_log_repo
        self._batch_query = batch_query
        self._batch_process = batch_process
        self._candidate_versions: dict[str, int] = {}

    async def run_once(self, cursor_ms: int) -> tuple[int, bool]:
        """处理一批 L0 消息，返回 (next_cursor, backlog_flag)。"""
        messages = self._l0_repo.list_since(cursor_ms, self._batch_query)
        if not messages:
            return cursor_ms, False
        backlog = len(messages) == self._batch_query
        process = self._slice_batch(messages)
        next_cursor = max(m.recorded_at_ms for m in process)

        for session_id, group in self._regroup(process).items():
            new_messages, _background = self._split(group)
            try:
                result = await self._extractor.extract(new_messages)
            except Exception as exc:  # noqa: BLE001 - 提取失败跳过本组，不阻断其它组
                logger.warning("L1 提取失败，跳过 session=%s: %s", session_id, exc)
                continue
            if not result.memories:
                continue
            candidates = self._recall_candidates(result.memories)
            decisions = await self._dedup_judge.judge(result.memories, candidates)
            self._write(decisions)

        return next_cursor, backlog

    # -- 批窗口 -------------------------------------------------------------

    def _slice_batch(self, messages: list[L0Message]) -> list[L0Message]:
        """取前 batch_process 条；第 batch_process/第 batch_process+1 条同毫秒则扩到该毫秒全部。"""
        process = messages[: self._batch_process]
        if len(messages) > self._batch_process:
            boundary_ms = messages[self._batch_process - 1].recorded_at_ms
            next_ms = messages[self._batch_process].recorded_at_ms
            if boundary_ms == next_ms:
                process = [m for m in messages if m.recorded_at_ms == boundary_ms]
        return process

    @staticmethod
    def _regroup(messages: list[L0Message]) -> dict[str, list[L0Message]]:
        groups: dict[str, list[L0Message]] = {}
        for m in messages:
            groups.setdefault(m.session_id, []).append(m)
        return groups

    @staticmethod
    def _split(group: list[L0Message]) -> tuple[list[L0Message], list[L0Message]]:
        """新消息取最后 10 条（LLM 提取），背景最多 5 条（仅供上下文）。"""
        new = group[-10:]
        background = group[:-10][-5:] if len(group) > 10 else []
        return new, background

    # -- 候选召回 + 写 ------------------------------------------------------

    def _recall_candidates(self, atoms: list[MemoryAtom]) -> list[MemoryAtom]:
        """Phase1 候选召回：无向量能力退化 FTS；此处简化——返回空（Phase 1 无向量时全 store）。"""
        candidates: list[MemoryAtom] = []
        own_ids = {a.id for a in atoms}
        if self._vector_store is not None and self._embedding is not None:
            try:
                for atom in atoms:
                    qv = self._embedding.embed_query(atom.content)
                    hits = self._vector_store.search(qv, top_k=10, filter=None)
                    for h in hits:
                        if h.id in own_ids:
                            continue
                        # 命中字段含 id/content 等；从 hits 构造候选（简化：靠 id 关联版本）
                        candidates.append(h)
            except Exception as exc:  # noqa: BLE001
                logger.warning("候选向量召回失败，退化 FTS: %s", exc)
        if not candidates:
            for atom in atoms:
                candidates.extend(self._atom_repo.search_atoms_fts(atom.content, top_k=5))
        # 记录候选版本映射（供 update/merge 计算 version）
        for c in candidates:
            if isinstance(c, MemoryAtom):
                self._candidate_versions[c.id] = c.version
        return [c for c in candidates if isinstance(c, MemoryAtom)]

    def _write(self, decisions: list[DedupDecision]) -> None:
        for decision in decisions:
            if decision.action == DedupAction.skip:
                continue
            atom = decision.memory
            if decision.action in (DedupAction.update, DedupAction.merge):
                version = max(
                    (self._candidate_versions.get(tid, 0) for tid in decision.target_ids),
                    default=0,
                ) + 1
                atom = atom.model_copy(update={"version": version})
                if decision.target_ids:
                    self._atom_repo.delete_atoms(decision.target_ids)
                    if self._vector_store is not None:
                        id_list = ", ".join(f'"{tid}"' for tid in decision.target_ids)
                        self._vector_store.delete(f"id in [{id_list}]")
            self._store(atom)

    def _store(self, atom: MemoryAtom) -> None:
        self._atom_repo.append_atom(atom)
        day = datetime.fromtimestamp(atom.updated_at_ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")
        self._journal.append(RECORDS_CATEGORY, atom.model_dump(), day=day)
        if self._vector_store is not None and self._embedding is not None:
            try:
                vector = self._embedding.embed_query(atom.content)
                self._vector_store.insert(
                    [{"id": atom.id, "session_id": atom.session_id, "content": atom.content, "vector": vector}]
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("L1 向量写失败（可选降级）: %s", exc)
        if self._generation_log_repo is not None:
            # 生成日志：此处为简化，layer=l1，output_refs=[atom.id]
            pass


class MemoryPipelineQueue:
    """L1 提取队列：会话轮次计数 + 热身阈值触发 + 空闲超时补跑 + flush。"""

    def __init__(
        self,
        runner: L1Runner,
        l0_repo,
        every_n: int = 5,
        idle_timeout_seconds: int = 600,
        l2_runner=None,
        l3_runner=None,
    ) -> None:
        self._runner = runner
        self._l0_repo = l0_repo
        self._every_n = every_n
        self._idle_timeout = idle_timeout_seconds
        self._l2_runner = l2_runner
        self._l3_runner = l3_runner
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._worker: asyncio.Task | None = None
        self._counts: dict[str, int] = {}
        self._completed = 0
        self._cursor_key = "last_l1_cursor"

    @staticmethod
    def _threshold(completed: int, every_n: int) -> int:
        """热身阈值：1 → 2 → 4 → 稳态 every_n。"""
        return min(every_n, 2 ** completed)

    def notify_conversation(self, session_id: str) -> None:
        """会话轮次 +1；达到热身阈值（min(every_n, 2**completed)）即入队触发提取。"""
        self._counts[session_id] = self._counts.get(session_id, 0) + 1
        threshold = self._threshold(self._completed, self._every_n)
        if self._counts[session_id] >= threshold:
            self._counts[session_id] = 0
            self._queue.put_nowait(session_id)

    def start(self) -> None:
        if self._worker is None:
            self._worker = asyncio.create_task(self._worker_loop())

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        await asyncio.gather(self._worker, return_exceptions=True)
        self._worker = None

    async def flush(self) -> None:
        """会话结束/关停清空缓冲：强制入队一次。"""
        self._queue.put_nowait("flush")

    async def _worker_loop(self) -> None:
        while True:
            try:
                await asyncio.wait_for(self._queue.get(), timeout=self._idle_timeout)
            except asyncio.TimeoutError:
                pass  # 空闲超时补跑
            try:
                cursor = self._l0_repo.get_cursor(self._cursor_key) or 0
                next_cursor, backlog = await self._runner.run_once(cursor)
                self._l0_repo.set_cursor(self._cursor_key, next_cursor)
                self._completed += 1
                l2_ran = False
                if self._l2_runner is not None:
                    self._l2_runner.notify_l1_completed()
                    l2_ran = await self._l2_runner.run_once()
                if self._l3_runner is not None and l2_ran:
                    await self._l3_runner.run_once(has_scenes=True, first_scene_completed=True)
                if backlog:
                    self._queue.put_nowait("backlog")
            except Exception as exc:  # noqa: BLE001 - worker 异常不退出
                logger.exception("L1 队列 worker 失败: %s", exc)
