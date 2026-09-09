"""通用 JSONL journal：append-only、按天分文件、线程锁串行化写。

一条 JSON 一行（`ensure_ascii=False`、`separators=(',', ':')`），用于 L0/L1
审计与灾难恢复，等价于 TS 版 `captureAtomically` 的轻量落地。
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Mapping


class JsonlJournalStore:
    """按天分文件的 append-only JSONL 存储。

    ``append`` 的 ``day`` 为必填 keyword-only（格式 ``YYYY-MM-DD``），由调用方
    从业务时间戳推导，原语不猜测时区或时间来源。
    """

    def __init__(self, root: Path) -> None:
        self._root = root
        self._lock = threading.Lock()

    def append(self, category: str, record: Mapping[str, Any], *, day: str) -> Path:
        """追加一条记录到 ``<root>/<category>/<day>.jsonl``，返回写入文件路径。"""
        with self._lock:
            path = self._root / category / f"{day}.jsonl"
            path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
            return path

    def read_day(self, category: str, day: str) -> list[dict]:
        """读取某天全部记录；文件缺失返回空列表。"""
        path = self._root / category / f"{day}.jsonl"
        if not path.is_file():
            return []
        with open(path, "r", encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]

    def list_days(self, category: str) -> list[str]:
        """返回某分类下已存在的日期（升序、去扩展名）。"""
        directory = self._root / category
        if not directory.is_dir():
            return []
        return sorted(p.stem for p in directory.glob("*.jsonl"))

    def delete_day(self, category: str, day: str) -> None:
        """删除整份某天文件；缺失时静默跳过。"""
        path = self._root / category / f"{day}.jsonl"
        path.unlink(missing_ok=True)
