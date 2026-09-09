"""Quiz file storage port (domain contract).

消费者：``QuizPaperService`` 需要把导出的试卷文件（md/json）写到磁盘，
并在下载时把数据库相对路径解析为绝对路径。
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class QuizFileStorage(Protocol):
    """试卷导出文件存储端口。"""

    def save(self, paper_id: str, filename: str, file_bytes: bytes) -> str:
        """保存试卷导出文件，返回相对存储根目录的路径（``quiz_papers/<id>/<filename>``）。"""
        ...

    def resolve(self, relative_path: str) -> Path | None:
        """把数据库相对路径解析为绝对路径；缺失或路径穿越时返回 ``None``。"""
        ...
