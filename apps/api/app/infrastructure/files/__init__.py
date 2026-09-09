"""文件存储基础设施。"""

from app.infrastructure.files.local_file_storage import (
    LocalFileStorage,
    get_local_file_storage,
)

__all__ = ["LocalFileStorage", "get_local_file_storage"]
