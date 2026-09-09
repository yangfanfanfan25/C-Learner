"""通用本地文件存储：scene_blocks / persona / 索引共用的文件 CRUD + 备份。"""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path


class LocalMemoryFileStorage:
    """基于本地文件系统的记忆文件存储（相对路径寻址）。

    备份命名为 ``<relative_path>.<UTC 时间戳>.bak``（字典序即时间序），按
    ``max_backups`` 裁剪最旧的超出部分。
    """

    def __init__(self, root: Path) -> None:
        self._root = root

    def write(self, relative_path: str, content: str) -> Path:
        target = self._root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    def read(self, relative_path: str) -> str | None:
        target = self._root / relative_path
        if not target.is_file():
            return None
        return target.read_text(encoding="utf-8")

    def exists(self, relative_path: str) -> bool:
        return (self._root / relative_path).is_file()

    def delete(self, relative_path: str) -> None:
        (self._root / relative_path).unlink(missing_ok=True)

    def list_files(self, subdir: str = "") -> list[str]:
        base = self._root / subdir
        if not base.is_dir():
            return []
        return sorted(p.name for p in base.iterdir() if p.is_file())

    def backup(self, relative_path: str, max_backups: int = 10) -> Path | None:
        """复制当前文件为带时间戳的 .bak；源缺失返回 None 并跳过。"""
        source = self._root / relative_path
        if not source.is_file():
            return None
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        dest = self._root / f"{relative_path}.{stamp}.bak"
        shutil.copy2(source, dest)
        self._prune_backups(relative_path, max_backups)
        return dest

    def _prune_backups(self, relative_path: str, max_backups: int) -> None:
        backups = sorted(self._root.glob(f"{relative_path}.*.bak"))
        if len(backups) <= max_backups:
            return
        for extra in backups[: len(backups) - max_backups]:
            extra.unlink(missing_ok=True)
