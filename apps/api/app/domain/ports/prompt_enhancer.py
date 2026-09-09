"""Domain port for prompt enhancement."""

from __future__ import annotations

from typing import Protocol


class PromptEnhancer(Protocol):
    async def enhance(self, content: str) -> str:
        """Return an improved version of a user prompt."""
        ...
