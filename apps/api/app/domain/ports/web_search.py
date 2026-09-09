"""Web search provider port (domain contract).

Defines the protocol and result types for external web search providers.
The chat workflow uses this port to obtain web context when the user
enables web search. Infrastructure implementations (e.g. Zhipu) live
under ``app.infrastructure.web_search``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class WebSearchSource:
    """A single web search result used for citation display."""

    id: str
    title: str
    url: str
    snippet: str


@dataclass(frozen=True)
class WebSearchResult:
    """Structured result returned by a web search provider."""

    context: str
    sources: list[WebSearchSource]


class WebSearchProvider(Protocol):
    """Minimal async interface for web search providers."""

    async def search(self, query: str, max_results: int) -> WebSearchResult:
        """Return web search results for *query*."""
        ...
