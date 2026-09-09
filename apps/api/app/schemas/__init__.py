# ==============================================================================
# Schema 包
# ==============================================================================
# 说明：
#   - 统一导出所有数据契约
#   - 便于其他模块导入
# ==============================================================================

from app.schemas.base import APIResponse, PaginatedData, PaginationParams
from app.schemas.health import HealthResponse
from app.schemas.chat import (
    ChatSource,
    ChatSessionCreate,
    ChatSessionResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatSessionDetail,
    PromptEnhanceRequest,
    PromptEnhanceResponse,
)
from app.schemas.documents import (
    DocumentChunkSummary,
    DocumentDetailResponse,
    DocumentProcessResponse,
    DocumentRecordResponse,
)
# 旧 exam schemas 已移除，使用 exam_record 替代
from app.schemas.knowledge_pipeline import (
    ChapterSection,
    DocumentChapter,
    KnowledgePipelineResult,
    KnowledgePoint,
    NormalizedChapterMarkdown,
    ParsedDocumentPage,
)
from app.schemas.domain import (
    DomainCreate,
    DomainUpdate,
    DomainResponse,
)
from app.schemas.chapter import (
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
)
from app.schemas.knowledge import (
    KnowledgeCatalogCreate,
    KnowledgeCatalogResponse,
    KnowledgeContentCreate,
    KnowledgeContentResponse,
    KnowledgeLinkCreate,
    KnowledgeLinkResponse,
    KnowledgeSourceCreate,
    KnowledgeSourceResponse,
    KnowledgeDetailResponse,
)
from app.schemas.exam_record import (
    ExamRecordCreate,
    ExamRecordResponse,
)
from app.schemas.review import (
    ReviewRecordCreate,
    ReviewRecordUpdate,
    ReviewRecordResponse,
)

__all__ = [
    # 基础
    "APIResponse",
    "PaginatedData",
    "PaginationParams",
    "HealthResponse",
    # Chat
    "ChatSource",
    "ChatSessionCreate",
    "ChatSessionResponse",
    "ChatMessageCreate",
    "ChatMessageResponse",
    "ChatSessionDetail",
    "PromptEnhanceRequest",
    "PromptEnhanceResponse",
    # Documents
    "DocumentChunkSummary",
    "DocumentDetailResponse",
    "DocumentProcessResponse",
    "DocumentRecordResponse",
    # Exam (旧版已移除，使用 exam_record)
    # Knowledge pipeline
    "ChapterSection",
    "DocumentChapter",
    "KnowledgePipelineResult",
    "KnowledgePoint",
    "NormalizedChapterMarkdown",
    "ParsedDocumentPage",
    # Domain
    "DomainCreate",
    "DomainUpdate",
    "DomainResponse",
    # Chapter
    "ChapterCreate",
    "ChapterUpdate",
    "ChapterResponse",
    # Knowledge
    "KnowledgeCatalogCreate",
    "KnowledgeCatalogResponse",
    "KnowledgeContentCreate",
    "KnowledgeContentResponse",
    "KnowledgeLinkCreate",
    "KnowledgeLinkResponse",
    "KnowledgeSourceCreate",
    "KnowledgeSourceResponse",
    "KnowledgeDetailResponse",
    # Exam Record
    "ExamRecordCreate",
    "ExamRecordResponse",
    # Review Record
    "ReviewRecordCreate",
    "ReviewRecordUpdate",
    "ReviewRecordResponse",
]
