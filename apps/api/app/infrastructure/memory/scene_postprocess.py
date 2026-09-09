"""L2 场景抽取后处理：软删清理、空文件删除、文件名规范化。"""

from __future__ import annotations

import re

from app.infrastructure.memory.scene_store import SceneBlockStore

_DELETED_MARKER = "[DELETED]"
_INVALID_FILENAME_CHARS = re.compile(r'[\s/\\:*?"<>|]')


class ScenePostProcessor:
    """对 LLM 维护后的场景块做规范化清理。"""

    def __init__(self, scene_store: SceneBlockStore) -> None:
        self._store = scene_store

    def cleanup(self) -> list[str]:
        """软删 [DELETED] 块 + 空正文块物理删除；返回被删文件名列表。"""
        removed: list[str] = []
        for meta in self._store.list_blocks():
            filename = meta.filename
            try:
                _, content = self._store.read_block(filename)
            except Exception:  # noqa: BLE001 - 损坏块跳过
                continue
            if _DELETED_MARKER in content or not content.strip():
                self._store.delete_block(filename)
                removed.append(filename)
        return removed

    def normalize_filenames(self) -> None:
        """把文件名里的空格/非法字符替换为下划线；重命名物理文件 + 重建索引。"""
        for meta in self._store.list_blocks():
            new_name = _INVALID_FILENAME_CHARS.sub("_", meta.filename).strip("_")
            if not new_name or new_name == meta.filename:
                continue
            # 读旧块 → 写新名 → 删旧名
            try:
                _, content = self._store.read_block(meta.filename)
            except Exception:  # noqa: BLE001
                continue
            self._store.write_block(new_name, meta, content)
            if new_name != meta.filename:
                self._store.delete_block(meta.filename)
