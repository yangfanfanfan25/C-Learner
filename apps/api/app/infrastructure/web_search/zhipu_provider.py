"""ZhipuAI web search provider.

Uses ZhipuAI's official WebSearch API for reliable search results.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse

from app.domain.ports.web_search import WebSearchProvider, WebSearchResult, WebSearchSource

logger = logging.getLogger(__name__)

_TITLE_MAX = 200
_SNIPPET_MAX = 500


class WebSearchError(Exception):
    """Raised when an external web search request fails."""


class ZhipuWebSearchProvider(WebSearchProvider):
    """Web search provider backed by ZhipuAI WebSearch API.

    Parameters
    ----------
    api_key:
        ZhipuAI API key. If not provided, reads from ZHIPU_API_KEY env var.
    search_engine:
        Search engine to use. Default is "search_pro".
    content_size:
        Content size for snippets: "low", "medium", "high". Default "high".
    timeout_seconds:
        Maximum seconds to wait for a single search call.
    client_factory:
        Callable returning a ZhipuAI client. Defaults to creating ZhipuAiClient.
    """

    def __init__(
        self,
        api_key: str | None = None,
        search_engine: str = "search_pro",
        content_size: str = "high",
        timeout_seconds: int = 30,
        client_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._api_key = api_key
        self._search_engine = search_engine
        self._content_size = content_size
        self._timeout_seconds = timeout_seconds
        self._client_factory = client_factory or self._default_client_factory

    def _default_client_factory(self) -> Any:
        from zhipuai import ZhipuAI

        return ZhipuAI(api_key=self._api_key)

    async def search(self, query: str, max_results: int) -> WebSearchResult:
        """Search using ZhipuAI WebSearch API."""
        normalized_query = query.strip()
        if not normalized_query:
            return WebSearchResult(context="No web search query was provided.", sources=[])

        try:
            raw_result = await asyncio.wait_for(
                asyncio.to_thread(self._call_api, normalized_query, max_results),
                timeout=self._timeout_seconds,
            )
            return self._normalize(raw_result)
        except TimeoutError as exc:
            raise WebSearchError(
                f"Web search timed out after {self._timeout_seconds}s"
            ) from exc
        except WebSearchError:
            raise
        except Exception as exc:
            raise WebSearchError(f"Web search failed ({type(exc).__name__})") from exc

    def _call_api(self, query: str, max_results: int) -> Any:
        """Call ZhipuAI WebSearch API synchronously."""
        client = self._client_factory()
        response = client.web_search.web_search(
            search_engine=self._search_engine,
            search_query=query,
            count=max_results,
            search_recency_filter="noLimit",
            content_size=self._content_size,
        )
        return response

    def _normalize(self, raw_result: Any) -> WebSearchResult:
        """Normalize ZhipuAI response to WebSearchResult."""
        sources: list[WebSearchSource] = []

        # Extract search results from response
        search_results = getattr(raw_result, "search_result", None) or []

        for item in search_results:
            # ZhipuAI returns SearchResultResp objects with attributes
            title = str(getattr(item, "title", "")).strip()
            url = str(getattr(item, "link", "")).strip()
            snippet = str(getattr(item, "content", "")).strip()

            if not self._is_valid_http_url(url):
                continue

            sources.append(
                WebSearchSource(
                    id=url,
                    title=(title or url)[:_TITLE_MAX],
                    url=url,
                    snippet=snippet[:_SNIPPET_MAX],
                )
            )

        if not sources:
            return WebSearchResult(
                context="No web search results were found.",
                sources=[],
            )

        context_parts = [
            f"[{i}] {s.title}\nURL: {s.url}\n{s.snippet}"
            for i, s in enumerate(sources, 1)
        ]
        return WebSearchResult(
            context="\n\n".join(context_parts),
            sources=sources,
        )

    @staticmethod
    def _is_valid_http_url(url: str) -> bool:
        parsed = urlparse(url)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
