"""Pydantic contracts for the document processing API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DocumentChunkSummary(BaseModel):
    """A single persisted knowledge chunk (without the raw vector)."""

    id: str
    title: str
    chapter: str
    section: str = ""
    content: str
    source_pages: list[int] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class DocumentRecordResponse(BaseModel):
    """A processed document record."""

    id: str
    filename: str
    course_name: str
    academic_year: int
    semester: int
    content_type: str
    file_size: int
    file_path: str | None = None
    status: str
    error_message: str | None = None
    chapter_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    processed_at: datetime | None = None

    model_config = {"from_attributes": True}


class DocumentDetailResponse(DocumentRecordResponse):
    """A document record plus its knowledge chunk summaries."""

    chunks: list[DocumentChunkSummary] = Field(default_factory=list)


class DocumentProcessResponse(BaseModel):
    """Result of processing a document through the knowledge pipeline."""

    document: DocumentRecordResponse
    chapter_count: int
    chunk_count: int
    indexed_count: int
