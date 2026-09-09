"""文本规范化接口（领域契约）。"""

from __future__ import annotations

from typing import Protocol

from app.schemas.knowledge_pipeline import DocumentChapter, NormalizedChapterMarkdown


class TextNormalizer(Protocol):
    """将原始章节文本规范化为结构化 Markdown。"""

    async def normalize(self, chapters: list[DocumentChapter]) -> list[NormalizedChapterMarkdown]:
        """规范化章节列表，返回稳定的 Markdown。"""
        ...
