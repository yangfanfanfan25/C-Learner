"""阶段5：将规范化的 Markdown 解析为结构化的知识点。"""

from __future__ import annotations

import re

from app.schemas.knowledge_pipeline import KnowledgePoint, NormalizedChapterMarkdown

# 标题正则：匹配 # ~ ######
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
# 字段正则：匹配 - 键：值 或 * 键：值
FIELD_RE = re.compile(r"^\s*[-*]\s*([^:：]+)\s*[:：]\s*(.*)$")
# 列表项正则：匹配 - 内容 或 * 内容
LIST_ITEM_RE = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
# 页码正则
PAGE_RE = re.compile(r"\d+")
NOISE_KW = ("主讲教师", "教师背景", "课程介绍", "课堂重要性", "学习目标", "致谢", "联系方式", "任课教师")


class MarkdownKnowledgePointParser:
    """将规范化的 Markdown 转换为知识点列表。"""

    def parse(
        self,
        document_id: str,
        chapters: list[NormalizedChapterMarkdown],
    ) -> list[KnowledgePoint]:
        """解析所有章节，返回知识点列表。"""
        points: list[KnowledgePoint] = []
        for chapter in chapters:
            points.extend(self._parse_chapter(document_id, chapter))
        return points

    def _parse_chapter(
        self,
        document_id: str,
        chapter_markdown: NormalizedChapterMarkdown,
    ) -> list[KnowledgePoint]:
        """解析单个章节的 Markdown，提取知识点。"""
        points: list[KnowledgePoint] = []
        chapter = chapter_markdown.chapter
        section = ""
        current: _PointBuffer | None = None
        section_list_items: list[str] = []

        def flush_current() -> None:
            """将当前缓冲区的内容转换为知识点。

            过滤掉没有答案（content 为空）的知识点：这类记录只有名称
            （如「云计算」仅给出定义名、无正文），不应入库或展示。
            """
            nonlocal current
            if current:
                point = current.to_point(document_id, chapter, section, chapter_markdown.source_pages)
                if point.knowledge.strip() and point.content.strip() and not _is_noise(point.knowledge, point.content):
                    points.append(point)
            current = None

        def flush_section_list_items() -> None:
            """将章节列表项转换为知识点。"""
            nonlocal section_list_items
            for item in section_list_items:
                if _is_noise(item, item):
                    continue
                points.append(
                    KnowledgePoint(
                        document_id=document_id,
                        chapter=chapter,
                        section=section,
                        knowledge=item,
                        content=item,
                        source_pages=chapter_markdown.source_pages,
                    )
                )
            section_list_items = []

        for raw_line in chapter_markdown.markdown.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # 匹配标题
            heading = HEADING_RE.match(line)
            if heading:
                level = len(heading.group(1))
                title = heading.group(2).strip()
                if level == 1:
                    flush_current()
                    flush_section_list_items()
                    chapter = title
                elif level == 2:
                    flush_current()
                    flush_section_list_items()
                    section = title
                elif level == 3:
                    flush_section_list_items()
                    flush_current()
                    current = _PointBuffer(knowledge=title)
                else:
                    if current:
                        current.content_lines.append(title)
                continue

            # 如果当前有知识点缓冲区，尝试解析字段或内容
            if current:
                field = FIELD_RE.match(line)
                if field:
                    current.apply_field(field.group(1).strip(), field.group(2).strip())
                else:
                    current.content_lines.append(LIST_ITEM_RE.sub(r"\1", line))
                continue

            # 匹配列表项
            list_item = LIST_ITEM_RE.match(line)
            if list_item and section:
                section_list_items.append(list_item.group(1).strip())

        flush_current()
        flush_section_list_items()
        return points


def _is_noise(knowledge: str, content: str) -> bool:
    text = f"{knowledge} {content}"
    return any(keyword in text for keyword in NOISE_KW)


class _PointBuffer:
    """知识点缓冲区，用于临时存储正在解析的知识点数据。"""

    def __init__(self, knowledge: str):
        self.knowledge = knowledge
        self.content_lines: list[str] = []
        self.source_pages: list[int] = []
        self.tags: list[str] = []

    def apply_field(self, key: str, value: str) -> None:
        """应用字段值到缓冲区。"""
        normalized_key = key.strip().lower()
        if normalized_key in {"内容", "content", "说明", "detail"}:
            if value:
                self.content_lines.append(value)
            return
        if normalized_key in {"来源页", "source_pages", "source pages", "页码"}:
            self.source_pages = [int(item) for item in PAGE_RE.findall(value)]
            return
        if normalized_key in {"标签", "tags"}:
            self.tags = [item.strip() for item in re.split(r"[,，、]", value) if item.strip()]
            return
        if value:
            self.content_lines.append(f"{key}: {value}")

    def to_point(
        self,
        document_id: str,
        chapter: str,
        section: str,
        fallback_pages: list[int],
    ) -> KnowledgePoint:
        """将缓冲区转换为知识点对象。"""
        content = "\n".join(line for line in self.content_lines if line).strip()
        return KnowledgePoint(
            document_id=document_id,
            chapter=chapter,
            section=section,
            knowledge=self.knowledge,
            content=content,
            source_pages=self.source_pages or fallback_pages,
            tags=self.tags,
        )
