"""阶段2：从解析后的文档文本中恢复章节结构。

支持多种文档格式的章节还原：
- PPTX：按 Part 标记切分
- PDF/DOCX/TXT/MD：按 Markdown 标题层级切分
- 无结构文档：整篇作为默认章节
"""

from __future__ import annotations

import re

from app.schemas.knowledge_pipeline import ChapterSection, DocumentChapter, ParsedDocumentPage

# Part 标记正则
PART_MARKER_RE = re.compile(r"^Part\s*(\d+)\s*$", re.IGNORECASE)

# Markdown 标题正则（# ~ ######）
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")

# 章节标题模式（按优先级排序）
CHAPTER_PATTERNS = [
    # 中文数字章节：第一章、第二章
    re.compile(r"^第[一二三四五六七八九十百千\d]+[章节篇课讲]"),
    # Part/部分标记（必须独立成行）
    re.compile(r"^Part\s*\d+\s*$", re.IGNORECASE),
    # 数字编号：一、二、
    re.compile(r"^[一二三四五六七八九十]+[、.]\s*\S"),
]

# 小节标题模式
SECTION_PATTERNS = [
    # 数字编号：1.、2.、3.（必须是短行，不能是长列表）
    re.compile(r"^\d+[、.]\s*[一-龥A-Z]"),
    # 带括号的数字：(1)、（一）
    re.compile(r"^[（(][一二三四五六七八九十\d]+[）)]\s*\S"),
]

# 需要跳过的行（噪音）
NOISE_PATTERNS = [
    re.compile(r"^!\[.*\]\(.*\)$"),  # 图片链接
    re.compile(r"^https?://"),  # URL
    re.compile(r"^[*\-=]{3,}$"),  # 分隔线
    re.compile(r"^\s*$"),  # 空行
    re.compile(r"^<!--.*-->$"),  # HTML注释（幻灯片标记等）
    re.compile(r"^#{1,6}\s*$"),  # 空标题
    re.compile(r"^[-•*]\s*$"),  # 空列表项
    re.compile(r"^#{1,6}\s*Notes\s*:?$", re.IGNORECASE),  # Notes: 标记
    re.compile(r"^#{1,6}\s*备注\s*:?$"),  # 备注标记
]

# 候选标题关键词（用于判断是否是标题）
TITLE_KEYWORDS = {
    "概述", "总结", "结论", "引言", "背景", "方法", "结果", "讨论",
    "特点", "分类", "定义", "原理", "应用", "优势", "劣势",
    "研究", "分析", "设计", "实现", "测试", "评估", "效益",
    "目标", "意义", "问题", "方案", "策略", "模式", "体系",
    "目录", "Contents", "大纲", "索引", "摘要", "参考文献",
}


class StructureRecoverer:
    """从文档文本中恢复章节结构。"""

    def recover(self, pages: list[ParsedDocumentPage]) -> list[DocumentChapter]:
        """从解析后的页面中恢复章节结构。"""
        # 合并所有页面文本
        full_text = "\n".join(page.text for page in pages if page.text)

        if not full_text.strip():
            return []

        # 按行分割
        lines = full_text.split("\n")

        # 检测文档结构特征，选择切分策略
        # 只有存在明确结构标记时才切分，否则整篇作为默认章节
        if self._has_part_markers(lines):
            chapters = self._split_by_part(lines)
        elif self._has_markdown_headings(lines):
            chapters = self._split_by_headings(lines)
        else:
            # 无明确结构标记，整篇作为默认章节，避免误切分
            chapters = [self._create_default_chapter(lines)]

        return chapters if chapters else [self._create_default_chapter(lines)]

    # ==========================================================================
    # 结构特征检测
    # ==========================================================================

    @staticmethod
    def _has_part_markers(lines: list[str]) -> bool:
        """检测是否包含 Part 标记。"""
        return any(PART_MARKER_RE.match(line.strip()) for line in lines)

    @staticmethod
    def _has_markdown_headings(lines: list[str]) -> bool:
        """检测是否包含 Markdown 标题。"""
        heading_count = sum(1 for line in lines if HEADING_RE.match(line.strip()))
        return heading_count >= 2

    # ==========================================================================
    # 切分策略 1：按 Part 标记切分
    # ==========================================================================

    def _split_by_part(self, lines: list[str]) -> list[DocumentChapter]:
        """按照 Part 标记切分章节。

        策略：收集所有 Part 标记位置，只保留有实际内容的 Part（内容超过10行）。
        """
        # 第一遍：收集所有 Part 标记的位置
        part_positions: list[dict] = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            match = PART_MARKER_RE.match(stripped)
            if match:
                part_num = match.group(1)
                part_positions.append({
                    "line_num": i,
                    "part_num": int(part_num),
                    "part_key": f"Part {part_num}",
                })

        if not part_positions:
            return []

        # 计算每个 Part 的内容行数
        for i, pos in enumerate(part_positions):
            start_line = pos["line_num"]
            end_line = part_positions[i + 1]["line_num"] if i + 1 < len(part_positions) else len(lines)
            content_lines = lines[start_line + 1:end_line]
            # 统计非空行数
            non_empty = sum(1 for line in content_lines if line.strip())
            pos["content_size"] = non_empty

        # 按 Part 编号分组，只保留内容最多的那个
        best_positions: dict[int, dict] = {}
        for pos in part_positions:
            part_num = pos["part_num"]
            if part_num not in best_positions or pos["content_size"] > best_positions[part_num]["content_size"]:
                best_positions[part_num] = pos

        # 过滤掉内容太少的 Part（少于10行）
        filtered_positions = [pos for pos in best_positions.values() if pos["content_size"] >= 10]

        # 按行号排序
        sorted_positions = sorted(filtered_positions, key=lambda x: x["line_num"])

        # 第二遍：按 Part 切分章节
        chapters: list[DocumentChapter] = []

        for i, pos in enumerate(sorted_positions):
            start_line = pos["line_num"]
            end_line = sorted_positions[i + 1]["line_num"] if i + 1 < len(sorted_positions) else len(lines)

            # 提取章节内容（跳过 Part 标记行本身）
            chapter_lines = lines[start_line + 1:end_line]

            # 构建章节
            chapter = self._build_chapter_from_lines(pos["part_key"], chapter_lines)
            chapters.append(chapter)

        return chapters

    # ==========================================================================
    # 切分策略 2：按 Markdown 标题切分
    # ==========================================================================

    def _split_by_headings(self, lines: list[str]) -> list[DocumentChapter]:
        """按照 Markdown 标题层级切分章节。

        规则：
        - `# 标题` 或 `## 标题` 作为章节标题
        - `### 标题` 作为小节标题
        - 第一个标题之前的正文归入首个章节的"正文"小节，不丢失
        """
        chapters: list[DocumentChapter] = []
        current_chapter: DocumentChapter | None = None
        current_section: ChapterSection | None = None
        preamble: list[str] = []  # 第一个标题之前的正文

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            heading = HEADING_RE.match(stripped)
            if heading:
                level = len(heading.group(1))
                title = heading.group(2).strip()

                # 过滤噪音标题
                if title.lower().startswith("notes") or title == "备注":
                    continue

                if current_chapter is None:
                    # 首个标题：创建章节，前置正文作为"正文"小节
                    current_chapter = DocumentChapter(title=title)
                    current_section = None
                    if preamble:
                        current_chapter.sections.append(
                            ChapterSection(title="正文", level=2, raw_text="\n".join(preamble))
                        )
                        preamble = []
                    if level >= 2:
                        # 无一级标题时，首个二级及以上标题充当章节内小节
                        current_section = ChapterSection(title=title, level=level)
                    continue

                if level == 1:
                    # 保存当前小节与章节
                    if current_section:
                        current_chapter.sections.append(current_section)
                    chapters.append(current_chapter)
                    current_chapter = DocumentChapter(title=title)
                    current_section = None
                elif level == 2:
                    # 作为小节
                    if current_section:
                        current_chapter.sections.append(current_section)
                    current_section = ChapterSection(title=title, level=2)
                else:  # level >= 3
                    # 三级及以下作为小节
                    if current_section is None:
                        current_section = ChapterSection(title=title, level=level)
                    else:
                        current_chapter.sections.append(current_section)
                        current_section = ChapterSection(title=title, level=level)
                continue

            # 非标题行，追加到当前小节或章节
            if current_chapter is None:
                # 尚未遇到标题，累积为前置正文（后续归入首个章节）
                preamble.append(stripped)
                continue
            if current_section:
                current_section.raw_text = self._append_line(current_section.raw_text, stripped)
            else:
                # 没有小节时，追加到章节级正文（复用已有的"正文"小节或新建）
                if current_section is None:
                    for existing in current_chapter.sections:
                        if existing.title == "正文":
                            current_section = existing
                            break
                if current_section is None:
                    current_section = ChapterSection(title="正文", level=2)
                    current_chapter.sections.append(current_section)
                current_section.raw_text = self._append_line(current_section.raw_text, stripped)

        # 保存最后一个章节
        if current_section and current_chapter:
            if current_section not in current_chapter.sections:
                current_chapter.sections.append(current_section)
        if current_chapter:
            chapters.append(current_chapter)

        # 兜底：全文无有效标题时，保留正文
        if not chapters and preamble:
            return [self._create_default_chapter(preamble)]

        return chapters

    # ==========================================================================
    # 切分策略 3：按规则模式切分
    # ==========================================================================

    def _split_by_patterns(self, lines: list[str]) -> list[DocumentChapter]:
        """使用规则模式识别章节标题。"""
        # 提取章节标题
        chapter_titles = self._extract_chapter_titles(lines)

        if not chapter_titles:
            return []

        # 合并重复标题
        chapter_titles = self._merge_duplicate_titles(chapter_titles)

        chapters: list[DocumentChapter] = []

        for i, title_info in enumerate(chapter_titles):
            start_line = title_info["line_num"]
            end_line = chapter_titles[i + 1]["line_num"] if i + 1 < len(chapter_titles) else len(lines)

            chapter_lines = lines[start_line:end_line]

            # 构建章节
            chapter = self._build_chapter_from_lines(title_info["text"], chapter_lines)
            chapters.append(chapter)

        return chapters

    def _extract_chapter_titles(self, lines: list[str]) -> list[dict]:
        """从文本中提取章节标题。"""
        candidates: list[dict] = []

        for i, line in enumerate(lines):
            stripped = line.strip()
            if not stripped or self._is_noise(stripped):
                continue

            level = self._detect_heading_level(stripped)
            if level > 0:
                candidates.append({
                    "line_num": i,
                    "text": stripped,
                    "level": level,
                })

        return candidates

    def _detect_heading_level(self, text: str) -> int:
        """检测文本的标题级别。返回 0 表示不是标题。"""
        # 过滤太长的文本（不是标题）
        if len(text) > 100:
            return 0

        # 检查显式 Markdown 标题
        if text.startswith("# "):
            return 1
        if text.startswith("## "):
            return 2
        if text.startswith("### "):
            return 3

        # 检查章节模式
        for pattern in CHAPTER_PATTERNS:
            if pattern.match(text):
                return 1

        # 检查小节模式（必须是短行）
        if len(text) <= 50:
            for pattern in SECTION_PATTERNS:
                if pattern.match(text):
                    return 2

        # 短文本（4-30字符）包含典型标题词
        if 4 <= len(text) <= 30:
            # 排除列表项（以 • 或 - 开头）
            if text.startswith(("•", "-", "*")):
                return 0
            if any(kw in text for kw in TITLE_KEYWORDS):
                return 2

        return 0

    @staticmethod
    def _is_noise(text: str) -> bool:
        """判断文本是否是噪音。"""
        return any(pattern.match(text) for pattern in NOISE_PATTERNS)

    @staticmethod
    def _merge_duplicate_titles(candidates: list[dict]) -> list[dict]:
        """合并重复出现的标题。"""
        if not candidates:
            return []

        from collections import Counter
        title_counts = Counter(c["text"] for c in candidates)

        merged = []
        seen = set()
        for c in candidates:
            title = c["text"]
            if title in seen:
                continue

            if title_counts[title] >= 2:
                merged.append(c)
                seen.add(title)
            elif c["level"] == 1:
                merged.append(c)
                seen.add(title)
            elif c["level"] == 2 and any(kw in title for kw in TITLE_KEYWORDS):
                merged.append(c)
                seen.add(title)

        return merged

    # ==========================================================================
    # 章节构建工具
    # ==========================================================================

    @staticmethod
    def _build_chapter_from_lines(title: str, lines: list[str]) -> DocumentChapter:
        """从行列表构建章节对象。"""
        # 清理空行，提取有效内容
        content_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped and not HEADING_RE.match(stripped):
                content_lines.append(stripped)

        # 提取小节（### 标题）
        sections = StructureRecoverer._extract_sections_from_lines(content_lines)

        # 如果没有小节，将整个内容作为一个小节
        if not sections and content_lines:
            sections.append(ChapterSection(
                title="正文",
                level=2,
                raw_text="\n".join(content_lines),
            ))

        return DocumentChapter(
            title=title,
            sections=sections,
        )

    @staticmethod
    def _extract_sections_from_lines(lines: list[str]) -> list[ChapterSection]:
        """从行列表提取 ### 小节。"""
        sections: list[ChapterSection] = []
        current_title: str | None = None
        current_lines: list[str] = []

        for line in lines:
            heading = HEADING_RE.match(line.strip())
            if heading and len(heading.group(1)) >= 2:
                # 保存上一个小节
                if current_title is not None:
                    sections.append(ChapterSection(
                        title=current_title,
                        level=3,
                        raw_text="\n".join(current_lines),
                    ))
                current_title = heading.group(2).strip()
                current_lines = []
            elif current_title is not None:
                current_lines.append(line)

        # 保存最后一个小节
        if current_title is not None:
            sections.append(ChapterSection(
                title=current_title,
                level=3,
                raw_text="\n".join(current_lines),
            ))

        return sections

    @staticmethod
    def _create_default_chapter(lines: list[str]) -> DocumentChapter:
        """创建默认章节（当无法识别章节结构时）。

        保留全部有效正文，避免内容丢失：第一有效行作为标题，其余作为正文小节。
        """
        # 过滤噪音行，保留有效内容
        valid_lines = [
            line.strip()
            for line in lines
            if line.strip() and not StructureRecoverer._is_noise(line.strip())
        ]

        if not valid_lines:
            return DocumentChapter(title="未命名章节", sections=[])

        # 第一有效行作为标题
        title = valid_lines[0]
        if len(title) > 50:
            title = title[:50] + "..."

        # 其余行作为正文（标题行不重复进正文）
        content = "\n".join(valid_lines[1:])

        sections = []
        if content.strip():
            sections.append(ChapterSection(
                title="正文",
                level=2,
                raw_text=content,
            ))

        return DocumentChapter(
            title=title,
            sections=sections,
        )

    @staticmethod
    def _append_line(existing: str, line: str) -> str:
        """将新行追加到现有文本中。"""
        return f"{existing}\n{line}".strip() if existing else line
