"""Knowledge document reader port (domain contract).

消费者：模拟练习工具 ``generate_quiz_paper`` 需要按前端 ``@`` 选择的文档 ID
读取其已入库知识切片（与「知识点 Markdown 下载」同一数据源，不重新解析原始文件），
作为出题模型的上下文注入。
"""

from __future__ import annotations

from typing import Protocol

from app.schemas.documents import DocumentRecordResponse


class KnowledgeDocumentReader(Protocol):
    """按文档 ID 读取已入库知识内容的端口。"""

    def get_documents(self, document_ids: list[str]) -> list[DocumentRecordResponse]:
        """按 ID 批量取文档记录（仅已完成处理且有知识切片的）。"""
        ...

    def read_markdown(
        self,
        document_ids: list[str],
        max_chars_per_doc: int = 20000,
    ) -> dict[str, str]:
        """读取指定文档已入库的知识切片，返回 ``doc_id -> 章节化 Markdown``。

        每文档截断到 ``max_chars_per_doc`` 字符，防止上下文膨胀。
        """
        ...
