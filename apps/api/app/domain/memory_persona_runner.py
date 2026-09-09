"""L3 画像层：PersonaTrigger 五条件 + L3Runner。"""

from __future__ import annotations

import logging

from app.domain.ports.memory import PersonaGeneratorPort
from app.schemas.memory import Persona

logger = logging.getLogger(__name__)


class PersonaTrigger:
    """L3 触发五条件（优先级 P1 → P4）。"""

    def __init__(self, trigger_every_n: int = 50) -> None:
        self._trigger_every_n = trigger_every_n
        self._memories_since_last_persona = 0

    def notify_new_memories(self, count: int) -> None:
        self._memories_since_last_persona += count

    def reset(self) -> None:
        self._memories_since_last_persona = 0

    def should_generate(
        self,
        *,
        explicit_request: bool = False,
        has_persona: bool = False,
        persona_body_lost: bool = False,
        has_scenes: bool = False,
        first_scene_completed: bool = False,
    ) -> bool:
        """按优先级判定是否触发 L3 画像生成。"""
        if explicit_request:
            return True  # P1
        if has_scenes and not has_persona:
            return True  # P2 冷启动
        if has_persona and persona_body_lost:
            return True  # P2.5 恢复
        if first_scene_completed:
            return True  # P3
        if self._memories_since_last_persona >= self._trigger_every_n:
            return True  # P4
        return False


class L3Runner:
    """L2 完成后按触发条件生成 L3 画像。"""

    def __init__(
        self,
        generator: PersonaGeneratorPort,
        trigger_every_n: int = 50,
    ) -> None:
        self._generator = generator
        self._trigger = PersonaTrigger(trigger_every_n=trigger_every_n)

    def notify_new_memories(self, count: int) -> None:
        self._trigger.notify_new_memories(count)

    async def run_once(
        self,
        *,
        explicit_request: bool = False,
        has_persona: bool = False,
        persona_body_lost: bool = False,
        has_scenes: bool = False,
        first_scene_completed: bool = False,
        changed_scenes: list[str] | None = None,
    ) -> Persona | None:
        """触发条件满足则生成画像；否则返回 None。"""
        if not self._trigger.should_generate(
            explicit_request=explicit_request,
            has_persona=has_persona,
            persona_body_lost=persona_body_lost,
            has_scenes=has_scenes,
            first_scene_completed=first_scene_completed,
        ):
            return None
        persona = await self._generator.generate("local", changed_scenes or [])
        self._trigger.reset()
        return persona
