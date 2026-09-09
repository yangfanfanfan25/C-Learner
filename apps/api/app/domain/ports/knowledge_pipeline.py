"""知识处理管道接口（领域契约）。"""

from __future__ import annotations

from typing import Protocol

from app.schemas.knowledge_pipeline import KnowledgePipelineResult


class KnowledgePipeline(Protocol):
    """执行文档到知识点的处理管道。"""

    async def run(self, document_id: str, filename: str, file_bytes: bytes) -> KnowledgePipelineResult:
        """执行管道，返回结构化的知识点。"""
        ...
