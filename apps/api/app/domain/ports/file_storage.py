"""Document file storage port used by the document processing service."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class DocumentFileStorage(Protocol):
    """持久化原始上传文件的端口。

    实现负责把文件字节写到磁盘，并支持按文档删除与路径解析。
    save 返回相对存储根目录的路径（如 ``<document_id>/<filename>``），
    由调用方写入数据库记录。
    """

    def save(self, document_id: str, filename: str, file_bytes: bytes) -> str:
        """保存原始文件，返回相对存储根目录的路径。"""
        ...

    def delete(self, document_id: str) -> None:
        """删除指定文档的原始文件；不存在时静默跳过。"""
        ...

    def resolve(self, relative_path: str) -> Path | None:
        """把数据库相对路径解析为绝对路径。

        文件缺失或路径穿越存储根目录时返回 ``None``（视为缺失），
        调用方据此返回 404，而不是暴露任意磁盘文件。
        """
        ...
