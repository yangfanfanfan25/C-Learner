"""本地磁盘原始文件存储实现。

布局：<files_root>/<document_id>/<原始文件名>
数据库仅记录相对路径 <document_id>/<filename>，便于整体移动数据目录。
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import Settings, get_settings


class LocalFileStorage:
    """基于本地文件系统的原始文件存储。

    保存时对文件名调用 ``Path.name`` 剥离路径成分，防止目录穿越。
    """

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, document_id: str, filename: str, file_bytes: bytes) -> str:
        """保存原始文件，返回相对 root 的路径（``<document_id>/<filename>``）。"""
        safe_name = Path(filename).name
        target_dir = self.root / document_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / safe_name).write_bytes(file_bytes)
        return f"{document_id}/{safe_name}"

    def delete(self, document_id: str) -> None:
        """删除文档的原始文件目录；目录不存在时静默跳过。"""
        target_dir = self.root / document_id
        if target_dir.exists():
            shutil.rmtree(target_dir)

    def resolve(self, relative_path: str) -> Path | None:
        """把数据库相对路径解析为绝对路径；缺失或越界时返回 ``None``。

        ``resolve`` 会跟随符号链接，因此能抵御 ``<document_id>/<filename>``
        中混入 ``..`` 或指向 root 外的软链造成的路径穿越。
        """
        candidate = (self.root / relative_path).resolve()
        if not candidate.is_relative_to(self.root.resolve()):
            return None
        if not candidate.is_file():
            return None
        return candidate


def get_local_file_storage(settings: Settings | None = None) -> LocalFileStorage:
    """工厂：确保 files 根目录存在并返回存储实例。"""
    if settings is None:
        settings = get_settings()
    settings.files_path.mkdir(parents=True, exist_ok=True)
    return LocalFileStorage(settings.files_path)
