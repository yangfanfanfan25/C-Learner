# ==============================================================================
# 领域模型包
# ==============================================================================
# 说明：
#   - ORM 模型已迁移至 app.infrastructure，此处仅做向后兼容的重新导出
#   - 统一导入模型，确保 Alembic 能通过 Base.metadata 发现所有表
# ==============================================================================

from app.infrastructure.domain import Domain
from app.infrastructure.chapter import Chapter
from app.infrastructure.knowledge_models import (
    KnowledgeCatalog,
    KnowledgeContent,
    KnowledgeLink,
    KnowledgeSource,
)
from app.infrastructure.exam import ExamRecord
from app.infrastructure.review_record import ReviewRecord
from app.infrastructure.chat import ChatMessage, ChatSession
from app.infrastructure.documents import DocumentChunk, DocumentRecord
from app.infrastructure.memory.models import (
    MemoryCursor,
    MemoryGenerationLog,
    MemoryL0Message,
    MemoryL1Atom,
)

__all__ = [
    "Domain",
    "Chapter",
    "KnowledgeCatalog",
    "KnowledgeContent",
    "KnowledgeLink",
    "KnowledgeSource",
    "ExamRecord",
    "ReviewRecord",
    "ChatSession",
    "ChatMessage",
    "DocumentRecord",
    "DocumentChunk",
    "MemoryL0Message",
    "MemoryCursor",
    "MemoryL1Atom",
    "MemoryGenerationLog",
]
