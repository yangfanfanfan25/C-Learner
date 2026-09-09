"""阶段4：使用 LLM 将解析后的章节文本规范化为结构化 Markdown。

使用 LangChain batch 调用实现并发处理。
实现 TextNormalizer 接口。
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from app.domain.ports.text_normalizer import TextNormalizer
from app.schemas.knowledge_pipeline import (
    ChapterOutput,
    DocumentChapter,
    KnowledgePointOutput,
    NormalizedChapterMarkdown,
    SectionOutput,
)

logger = logging.getLogger(__name__)

class LangChainTextNormalizer:
    """调用 LangChain LLM 对每个章节进行规范化处理。

    使用 LangChain ``abatch`` 调用并发处理，限制由应用配置注入。
    LLM 输出 JSON 格式，使用 Pydantic 模型约束。
    """

    def __init__(self, model: BaseChatModel, max_concurrency: int):
        self.model = model
        self.max_concurrency = max_concurrency

    async def normalize(self, chapters: list[DocumentChapter]) -> list[NormalizedChapterMarkdown]:
        """规范化所有章节，返回 Markdown 列表。"""
        if not chapters:
            return []

        message_batches = [self._build_messages(chapter) for chapter in chapters]
        results = await self.model.abatch(
            message_batches,
            config={"max_concurrency": self.max_concurrency},
            return_exceptions=True,
        )

        # 处理结果，过滤异常
        outputs: list[NormalizedChapterMarkdown] = []
        failures: list[str] = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error("章节 %s 规范化失败: %s", chapters[i].title, result)
                # 降级处理：返回原始文本
                outputs.append(NormalizedChapterMarkdown(
                    chapter=chapters[i].title,
                    source_pages=chapters[i].source_pages,
                    markdown=self._fallback_markdown(chapters[i]),
                ))
                failures.append(f"{chapters[i].title}: {type(result).__name__}: {result}")
            else:
                outputs.append(self._normalize_response(chapters[i], result))

        if failures:
            raise RuntimeError("LLM 批处理失败，需重新总结；" + " | ".join(failures))
        return outputs

    def _build_messages(self, chapter: DocumentChapter) -> list[SystemMessage | HumanMessage]:
        return [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=self._build_prompt(chapter)),
        ]

    def _normalize_response(
        self,
        chapter: DocumentChapter,
        response: object,
    ) -> NormalizedChapterMarkdown:
        """Validate one batch result and convert it to normalized Markdown."""
        raw_text = message_content_to_text(getattr(response, "content", response))

        # 解析 JSON 并转换为 Markdown
        try:
            chapter_output = self._parse_json_response(raw_text)
            markdown = self._convert_to_markdown(chapter_output)
        except Exception as e:
            logger.warning("JSON 解析失败，使用原始输出: %s", e)
            markdown = f"# {chapter.title}\n"

        return NormalizedChapterMarkdown(
            chapter=chapter.title,
            source_pages=chapter.source_pages,
            markdown=markdown,
        )

    @staticmethod
    def _get_system_prompt() -> str:
        """获取系统提示词。"""
        return """你是课程资料整理助手。你的任务是把解析后的原文整理成结构化的 JSON 格式。

输出要求：
1. 必须是合法的 JSON 格式
2. 每个可独立复习的概念、事实、流程、分类、对比项都作为一个知识点
3. 不要增加原文没有的信息
4. 不要做重要性评分
5. 每个知识点都必须从“可分辨、可区分、可记忆”的角度提取正文关键字，并写入 tags
6. tags 必须是 content 原文中实际出现的关键短语，优先选择具有区分度的特征词或动作词，不能重复 knowledge 标题
7. 例如“云计算服务是在线平台，能够通过互联网按需提供各种 IT 资源和功能，包含：存储、计算、网络、数据库、分析、应用程序等”，tags 应为“在线平台”“按需提供”等，而不是“云计算服务”
8. 如果没有合适关键字，tags 返回空数组"""

    @staticmethod
    def _build_prompt(chapter: DocumentChapter) -> str:
        """构建规范化提示词。"""
        sections = []
        for section in chapter.sections:
            sections.append(
                f"## {section.title}\n"
                f"来源页: {', '.join(str(page) for page in section.source_pages)}\n"
                f"{section.raw_text}"
            )
        source = "\n\n".join(sections)

        return f"""请把下面一个章节的解析原文规范化为 JSON 格式。

输出 JSON 结构：
```json
{{
  "chapter": "章节标题",
  "sections": [
    {{
      "title": "小节标题",
      "knowledge_points": [
        {{
          "knowledge": "知识点名称",
          "content": "知识点内容",
          "source_pages": [1, 2],
          "tags": ["正文关键短语1", "正文关键短语2"]
        }}
      ]
    }}
  ]
}}
```

章节标题：{chapter.title}
章节页码：{', '.join(str(page) for page in chapter.source_pages)}

再次强调：tags 只能从对应 content 原文中选取有区分度、便于记忆的短语，不能填写 knowledge 标题。

解析原文：
{source}"""

    @staticmethod
    def _parse_json_response(text: str) -> ChapterOutput:
        """解析 LLM 返回的 JSON。"""
        # 移除代码围栏
        cleaned = strip_code_fence(text)

        # 尝试解析 JSON
        data = json.loads(cleaned)

        # 验证并转换为 Pydantic 模型
        return ChapterOutput.model_validate(data)

    @staticmethod
    def _convert_to_markdown(chapter_output: ChapterOutput) -> str:
        """将 ChapterOutput 转换为 Markdown 格式。"""
        lines = [f"# {chapter_output.chapter}", ""]

        for section in chapter_output.sections:
            lines.append(f"## {section.title}")
            lines.append("")

            for point in section.knowledge_points:
                lines.append(f"### {point.knowledge}")
                lines.append("")
                lines.append(f"- 内容：{point.content}")
                if point.source_pages:
                    pages_str = ", ".join(str(p) for p in point.source_pages)
                    lines.append(f"- 来源页：{pages_str}")
                if point.tags:
                    tags_str = "、".join(point.tags)
                    lines.append(f"- 标签：{tags_str}")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def _fallback_markdown(chapter: DocumentChapter) -> str:
        """降级处理：生成简单的 Markdown。"""
        lines = [f"# {chapter.title}", ""]

        for section in chapter.sections:
            lines.append(f"## {section.title}")
            lines.append("")
            if section.raw_text:
                lines.append(section.raw_text)
            lines.append("")

        return "\n".join(lines)


def message_content_to_text(content: object) -> str:
    """将 LangChain 消息内容转换为纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text") or item.get("content")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content)


def strip_code_fence(text: str) -> str:
    """移除 Markdown 代码围栏。"""
    stripped = text.strip()
    if stripped.startswith("```json"):
        stripped = stripped[7:]
    elif stripped.startswith("```markdown"):
        stripped = stripped[11:]
    elif stripped.startswith("```md"):
        stripped = stripped[5:]
    elif stripped.startswith("```"):
        stripped = stripped[3:]
    if stripped.endswith("```"):
        stripped = stripped[:-3]
    return stripped.strip()
