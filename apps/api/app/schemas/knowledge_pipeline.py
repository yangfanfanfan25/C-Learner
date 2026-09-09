"""Pydantic contracts for the document-to-knowledge-chunks pipeline.

The pipeline parses an uploaded document, restores chapter
structure, normalizes chapters into Markdown with an LLM, and finally
splits the Markdown into structured knowledge chunks.
"""

from __future__ import annotations

from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


PipelineStage = Literal[
    "uploaded",
    "document_parse",
    "structure",
    "normalize_markdown",
    "parse_markdown",
    "completed",
    "failed",
]


class ParsedDocumentPage(BaseModel):
    page_id: int = Field(ge=1)
    text: str = ""


class ChapterSection(BaseModel):
    title: str
    level: int = Field(default=2, ge=1, le=6)
    source_pages: list[int] = Field(default_factory=list)
    raw_text: str = ""


class DocumentChapter(BaseModel):
    title: str
    source_pages: list[int] = Field(default_factory=list)
    sections: list[ChapterSection] = Field(default_factory=list)


class NormalizedChapterMarkdown(BaseModel):
    chapter: str
    source_pages: list[int] = Field(default_factory=list)
    markdown: str


class KnowledgePoint(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    document_id: str
    chapter: str
    section: str = ""
    knowledge: str
    content: str = ""
    source_pages: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class KnowledgePipelineResult(BaseModel):
    document_id: str
    filename: str
    stage: PipelineStage
    chapters: list[DocumentChapter] = Field(default_factory=list)
    normalized_markdown: list[NormalizedChapterMarkdown] = Field(default_factory=list)
    knowledge_points: list[KnowledgePoint] = Field(default_factory=list)


# ==============================================================================
# LLM 输出的 Pydantic 模型（用于结构化输出）
# ==============================================================================


class KnowledgePointOutput(BaseModel):
    """单个知识点的 LLM 输出结构。"""
    knowledge: str = Field(description="知识点名称")
    content: str = Field(description="知识点内容")
    source_pages: list[int] = Field(default_factory=list, description="来源页码")
    tags: list[str] = Field(default_factory=list, description="标签")


class SectionOutput(BaseModel):
    """小节的 LLM 输出结构。"""
    title: str = Field(description="小节标题")
    knowledge_points: list[KnowledgePointOutput] = Field(
        default_factory=list,
        description="该小节下的知识点列表",
    )


class ChapterOutput(BaseModel):
    """章节的 LLM 输出结构（JSON 格式）。"""
    chapter: str = Field(description="章节标题")
    sections: list[SectionOutput] = Field(
        default_factory=list,
        description="章节下的小节列表",
    )
