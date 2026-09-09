"""L2 场景层 runner：级联节流定时器 + 增量读 L1 + skipped。"""

from __future__ import annotations

import logging
import time

from app.domain.ports.memory import SceneExtractorPort
from app.schemas.memory import MemoryAtom, SceneExtractOutcome

logger = logging.getLogger(__name__)


def _now_ms() -> int:
    return int(time.time() * 1000)


class L2Runner:
    """L1 完成后节流调度 L2：读增量 L1 记忆 → 场景抽取。"""

    def __init__(
        self,
        atom_repo,
        extractor: SceneExtractorPort,
        delay_seconds: int = 10,
        min_interval_seconds: int = 900,
        max_interval_seconds: int = 3600,
    ) -> None:
        self._atom_repo = atom_repo
        self._extractor = extractor
        self._delay_ms = delay_seconds * 1000
        self._min_interval_ms = min_interval_seconds * 1000
        self._max_interval_ms = max_interval_seconds * 1000
        self._last_l2_cursor = 0
        self._last_l2_ms = 0
        self._desired_ms: int | None = None

    def _compute_desired_ms(self, now_ms: int, last_l2_ms: int) -> int:
        """desired = max(now + delay, last_l2 + min_interval)。"""
        return max(now_ms + self._delay_ms, last_l2_ms + self._min_interval_ms)

    def notify_l1_completed(self, now_ms: int | None = None) -> None:
        """L1 完成 → 推进定时器；downward-only（只许提前，不许推后）。"""
        now_ms = now_ms if now_ms is not None else _now_ms()
        candidate = self._compute_desired_ms(now_ms, self._last_l2_ms)
        if self._desired_ms is None or candidate < self._desired_ms:
            self._desired_ms = candidate

    async def run_once(self, now_ms: int | None = None) -> bool:
        """到时间则读增量 L1 并抽取；无新记忆返回 False（skipped）。"""
        now_ms = now_ms if now_ms is not None else _now_ms()
        if self._desired_ms is None or now_ms < self._desired_ms:
            return False
        atoms = self._atom_repo.list_atoms_since(self._last_l2_cursor, limit=1000)
        if not atoms:
            return False  # skipped
        outcome = await self._extractor.extract("local", atoms)
        self._last_l2_cursor = max(a.updated_at_ms for a in atoms)
        self._last_l2_ms = now_ms
        self._desired_ms = None
        logger.info("L2 场景抽取完成: changed=%s", outcome.changed_scenes)
        return True
