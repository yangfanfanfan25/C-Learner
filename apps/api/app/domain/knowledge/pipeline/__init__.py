"""文档到 Markdown 的知识处理管道。

重新导出 KnowledgePipeline 接口以保持向后兼容。
具体实现位于 app.infrastructure.knowledge。
"""

from app.domain.ports.knowledge_pipeline import KnowledgePipeline

__all__ = ["KnowledgePipeline"]
