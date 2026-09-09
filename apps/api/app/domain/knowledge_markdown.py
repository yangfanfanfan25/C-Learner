"""知识切片 → Markdown 的纯函数导出。

从文档路由（原 ``documents.py::_build_knowledge_markdown``）提取为共享纯函数，
供「知识点 Markdown 下载」与模拟练习的 ``KnowledgeDocumentReader`` 复用，
保证两处输出一致。
"""

from __future__ import annotations

from app.schemas.documents import DocumentDetailResponse


def build_knowledge_markdown(detail: DocumentDetailResponse) -> str:
    """把知识切片按章节分组导出为 Markdown 文本（无行为变更的提取）。"""
    lines = [f"# {detail.filename}", "", f"> 共 {len(detail.chunks)} 个知识切片", ""]
    for chunk in detail.chunks:
        lines.append(f"## § {chunk.chapter}")
        lines.append("")
        if chunk.section:
            lines.append(f"### ▸ {chunk.section}")
            lines.append("")
        lines.append(f"#### {chunk.title}")
        meta: list[str] = []
        if chunk.source_pages:
            meta.append("来源页：" + "、".join(str(page) for page in chunk.source_pages))
        if chunk.tags:
            meta.append("标签：" + "、".join(chunk.tags))
        if meta:
            lines.append("- " + "；".join(meta))
            lines.append("")
        if chunk.content:
            lines.append(chunk.content)
            lines.append("")
    return "\n".join(lines)
