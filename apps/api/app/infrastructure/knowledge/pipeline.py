"""简单的顺序管道，用于文档到知识点的处理。

替代原有的 LangGraph 编排方案，采用直观的顺序执行方式。
实现 KnowledgePipeline 接口。
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.domain.knowledge.pipeline.markdown_point_parser import MarkdownKnowledgePointParser
from app.domain.knowledge.pipeline.structure_recoverer import StructureRecoverer
from app.domain.ports.document_converter import DocumentConverter
from app.domain.ports.knowledge_pipeline import KnowledgePipeline
from app.domain.ports.text_normalizer import TextNormalizer
from app.infrastructure.knowledge.document_converter import MarkItDownDocumentConverter
from app.infrastructure.knowledge.text_normalizer import LangChainTextNormalizer
from app.schemas.knowledge_pipeline import KnowledgePipelineResult

logger = logging.getLogger(__name__)


@dataclass
class SimpleKnowledgePipeline:
    """顺序管道：文档 → 结构恢复 → Markdown 规范化 → 知识点提取。

    使用简单的顺序执行方式实现 KnowledgePipeline 接口。
    """

    model: object  # BaseChatModel，避免领域层依赖 langchain
    settings: Settings | None = None
    document_converter: DocumentConverter | None = None
    text_normalizer: TextNormalizer | None = None
    structure_recoverer: StructureRecoverer | None = None
    markdown_parser: MarkdownKnowledgePointParser | None = None

    def __post_init__(self) -> None:
        settings = self.settings or get_settings()
        self.settings = settings
        self.document_converter = self.document_converter or MarkItDownDocumentConverter()
        self.text_normalizer = self.text_normalizer or LangChainTextNormalizer(
            self.model,
            max_concurrency=settings.document_llm_max_concurrency,
        )
        self.structure_recoverer = self.structure_recoverer or StructureRecoverer()
        self.markdown_parser = self.markdown_parser or MarkdownKnowledgePointParser()

    async def run(self, document_id: str, filename: str, file_bytes: bytes) -> KnowledgePipelineResult:
        """顺序执行管道，返回结构化的知识点。"""
        logger.info("管道启动，文档：%s", filename)

        # 阶段1：文档解析（markitdown）
        logger.info("阶段1：文档解析")
        parsed_pages = await asyncio.to_thread(
            self.document_converter.convert,
            file_bytes,
            filename,
        )

        # 阶段2：结构恢复
        logger.info("阶段2：结构恢复")
        chapters = await asyncio.to_thread(self.structure_recoverer.recover, parsed_pages)

        # 阶段3：Markdown 规范化
        logger.info("阶段3：Markdown 规范化")
        normalized_markdown = await self.text_normalizer.normalize(chapters)

        # 阶段4：知识点提取
        logger.info("阶段4：知识点提取")
        knowledge_points = await asyncio.to_thread(
            self.markdown_parser.parse,
            document_id,
            normalized_markdown,
        )

        logger.info("管道完成，文档：%s（%d 个知识点）", filename, len(knowledge_points))

        return KnowledgePipelineResult(
            document_id=document_id,
            filename=filename,
            stage="completed",
            chapters=chapters,
            normalized_markdown=normalized_markdown,
            knowledge_points=knowledge_points,
        )
