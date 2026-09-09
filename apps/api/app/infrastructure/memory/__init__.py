"""长期记忆基础设施原语（Phase 0：通用存储原语，无业务契约）。

导出实现与工厂，不导出 domain 协议（backend.md §4）。
"""

from app.infrastructure.memory.capture import (
    MemoryCaptureService,
    close_l1_memory_vector_store,
    get_l1_memory_vector_store,
    l1_collection_fields,
)
from app.infrastructure.memory.journal import JsonlJournalStore
from app.infrastructure.memory.files import LocalMemoryFileStorage
from app.infrastructure.memory.fts import FtsHit, create_fts5_table, fts_search
from app.infrastructure.memory.models import MemoryCursor, MemoryL0Message
from app.infrastructure.memory.sanitize import sanitize_text, should_capture_l0, strip_code_blocks
from app.infrastructure.memory.sqlite_repository import SqliteMemoryRepository, init_fts
from app.infrastructure.memory.dedup import LangChainDedupJudge
from app.infrastructure.memory.extractor import LangChainAtomExtractor
from app.infrastructure.memory.scene import LangChainSceneExtractor
from app.infrastructure.memory.scene_postprocess import ScenePostProcessor
from app.infrastructure.memory.scene_store import SceneBlockStore
from app.infrastructure.memory.persona import (
    LangChainPersonaGenerator,
    escape_xml_tags,
    reattach_navigation,
    strip_navigation,
)

__all__ = [
    "JsonlJournalStore",
    "LocalMemoryFileStorage",
    "FtsHit",
    "create_fts5_table",
    "fts_search",
    "MemoryCaptureService",
    "sanitize_text",
    "strip_code_blocks",
    "should_capture_l0",
    "SqliteMemoryRepository",
    "init_fts",
    "MemoryCursor",
    "MemoryL0Message",
    "l1_collection_fields",
    "get_l1_memory_vector_store",
    "close_l1_memory_vector_store",
    "LangChainAtomExtractor",
    "LangChainDedupJudge",
    "LangChainSceneExtractor",
    "ScenePostProcessor",
    "SceneBlockStore",
    "LangChainPersonaGenerator",
    "escape_xml_tags",
    "reattach_navigation",
    "strip_navigation",
]
