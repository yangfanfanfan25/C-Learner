"""L2 场景块文件存储：scene_blocks/*.md（META front-matter + 正文）+ scene_index.json。"""

from __future__ import annotations

from app.infrastructure.memory.files import LocalMemoryFileStorage
from app.schemas.memory import SceneBlockMeta, SceneIndex

SCENE_DIR = "scene_blocks"
INDEX_FILENAME = "scene_index.json"

# front-matter 中需要转成整型的字段（文件中以文本存储）
_INT_FIELDS = ("heat", "updated_at_ms", "evidence_count")
_FLOAT_FIELDS = ("confidence",)


def _serialize_block(meta: SceneBlockMeta, content: str) -> str:
    return (
        f"---\nsummary: {meta.summary}\nheat: {meta.heat}\n"
        f"updated_at_ms: {meta.updated_at_ms}\nactivity: {meta.activity.value if meta.activity else ''}\n"
        f"subject: {meta.subject or ''}\nconfidence: {meta.confidence}\n"
        f"evidence_count: {meta.evidence_count}\n---\n\n{content}"
    )


def _parse_block(text: str) -> tuple[dict, str]:
    """解析 front-matter；返回 (meta_dict, content)。

    ``heat``/``updated_at_ms`` 在文件中以文本存储，这里强制转成 int，
    使 ``SceneBlockMeta(**raw_meta)`` 可直接构造。
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {}, text
    meta: dict = {}
    for line in lines[1:end]:
        if ":" in line:
            k, v = line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if k in _INT_FIELDS:
                try:
                    meta[k] = int(v)
                except ValueError:
                    meta[k] = 0
            elif k in _FLOAT_FIELDS:
                try:
                    meta[k] = float(v)
                except ValueError:
                    meta[k] = 0.0
            elif k in {"activity", "subject"}:
                meta[k] = v or None
            else:
                meta[k] = v
    content = "\n".join(lines[end + 1 :]).lstrip("\n")
    return meta, content


class SceneBlockStore:
    """scene_blocks 文件 + scene_index.json 的读写。"""

    def __init__(self, file_storage: LocalMemoryFileStorage) -> None:
        self._fs = file_storage

    def _path(self, filename: str) -> str:
        return f"{SCENE_DIR}/{filename}"

    def list_blocks(self) -> list[SceneBlockMeta]:
        """返回 scene_index.json 里的块元信息；index 缺失则从文件重建。"""
        raw = self._fs.read(INDEX_FILENAME)
        if raw is None:
            return self.sync_index().scenes
        index = SceneIndex.model_validate_json(raw)
        return index.scenes

    def read_block(self, filename: str) -> tuple[SceneBlockMeta, str]:
        text = self._fs.read(self._path(filename))
        if text is None:
            raise FileNotFoundError(f"场景块不存在: {filename}")
        meta, content = _parse_block(text)
        meta = SceneBlockMeta(filename=filename, **meta)
        return meta, content

    def write_block(self, filename: str, meta: SceneBlockMeta, content: str) -> None:
        self._fs.write(self._path(filename), _serialize_block(meta, content))
        self.sync_index()

    def delete_block(self, filename: str) -> None:
        self._fs.delete(self._path(filename))
        self.sync_index()

    def sync_index(self) -> SceneIndex:
        """扫描 scene_blocks/*.md 重建 scene_index.json。"""
        filenames = self._fs.list_files(SCENE_DIR)
        metas: list[SceneBlockMeta] = []
        for fn in sorted(filenames):
            text = self._fs.read(self._path(fn))
            if text is None:
                continue
            raw_meta, _ = _parse_block(text)
            try:
                metas.append(SceneBlockMeta(filename=fn, **raw_meta))
            except Exception:  # noqa: BLE001 - 跳过损坏块
                continue
        index = SceneIndex(scenes=metas)
        self._fs.write(INDEX_FILENAME, index.model_dump_json())
        return index
