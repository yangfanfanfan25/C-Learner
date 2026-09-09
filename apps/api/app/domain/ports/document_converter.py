"""文档转换接口（领域契约）。"""

from __future__ import annotations

from typing import Protocol

from app.schemas.knowledge_pipeline import ParsedDocumentPage


class DocumentConverter(Protocol):
    """将上传的文件字节转换为可处理的页面。"""

    def convert(self, file_bytes: bytes, filename: str) -> list[ParsedDocumentPage]:
        """解析文件字节，返回可处理的页面列表。"""
        ...
