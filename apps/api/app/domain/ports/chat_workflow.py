"""Chat workflow runner port (domain contract)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any, Literal, Protocol


@dataclass(frozen=True)
class ChatWorkflowEvent:
    """A single event emitted while streaming a chat workflow.

    ``type`` values:

    - ``status``: phase indicator (``searching_knowledge`` / ``searching_web`` /
      ``generating`` ...).
    - ``step``: one tool lifecycle log entry. The payload includes a stable
      ``id``, ``kind`` (``tool_start`` / ``tool_result``), ``message``, tool
      ``args`` and the actual ``output`` when finished. Events come from
      LangGraph's native ``tools`` stream mode and are never rebuilt from
      incremental model ``tool_calls`` chunks.
      Step events are ephemeral UI logs and must NOT be persisted into the
      final assistant message content.
    - ``sources``: retrieval sources.
    - ``token``: a chunk of the answer text.
    - ``quiz``: a mock practice paper payload (``paper_id`` / ``downloads`` /
      ``questions`` ...), emitted once per practice-mode turn by the
      ``DeepAgentsPracticeWorkflowRunner``.
    - ``quiz_token``: a chunk of the quiz-generation model output text
      (streamed while ``generate_quiz_paper`` is writing the paper). It is
      ephemeral progress output for the frontend and must NOT be persisted
      into the final assistant message content.
    - ``quiz_reset``: clear the current quiz-generation draft before a retry,
      so failed-attempt tokens are not appended to the next attempt.
    """

    type: Literal[
        "status",
        "step",
        "sources",
        "token",
        "quiz",
        "quiz_token",
        "quiz_reset",
    ]
    data: Any


class ChatWorkflowRunner(Protocol):
    """Domain-facing interface for streaming chat workflow events."""

    async def stream_events(
        self,
        session_id: str,
        question: str,
        document_ids: list[str] | None = None,
        capabilities: list[str] | None = None,
    ) -> AsyncIterator[ChatWorkflowEvent]:
        """Yield workflow events for a single user question.

        ``document_ids``: documents picked via ``@`` in the composer; the
        practice runner injects their processed knowledge as quiz context.
        """
        ...
