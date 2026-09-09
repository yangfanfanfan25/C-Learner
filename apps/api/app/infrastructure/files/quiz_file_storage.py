"""本地磁盘试卷导出文件存储实现。

布局：<files_root>/quiz_papers/<paper_id>/<文件名>
数据库仅记录相对路径，便于整体移动数据目录。
与 ``LocalFileStorage`` 共享同一 files 根目录（组合根注入相同 root）。
"""

from __future__ import annotations

from pathlib import Path

from app.core.config import Settings, get_settings


class LocalQuizFileStorage:
    """基于本地文件系统的试卷导出文件存储。"""

    def __init__(self, root: Path) -> None:
        self.root = root

    def save(self, paper_id: str, filename: str, file_bytes: bytes) -> str:
        safe_name = Path(filename).name
        target_dir = self.root / "quiz_papers" / paper_id
        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / safe_name).write_bytes(file_bytes)
        return f"quiz_papers/{paper_id}/{safe_name}"

    def resolve(self, relative_path: str) -> Path | None:
        candidate = (self.root / relative_path).resolve()
        if not candidate.is_relative_to(self.root.resolve()):
            return None
        if not candidate.is_file():
            return None
        return candidate


def get_local_quiz_file_storage(settings: Settings | None = None) -> LocalQuizFileStorage:
    """工厂：确保 files 根目录存在并返回存储实例。"""
    if settings is None:
        settings = get_settings()
    settings.files_path.mkdir(parents=True, exist_ok=True)
    return LocalQuizFileStorage(settings.files_path)
