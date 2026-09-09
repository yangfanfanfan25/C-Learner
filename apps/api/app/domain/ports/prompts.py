"""System prompt provider port (domain contract).

消费者：deepagents 聊天运行器在组装智能体时，按功能模式获取系统提示词。
提示词文本的唯一出处是 ``app/infrastructure/prompts/chat_prompts.py``，
运行器与工具不内嵌任何提示词常量，统一经本端口注入。

本协议只定义已有真实消费者的方法；后续新增功能的提示词，
在对应功能开发时再扩展（遵循最小协议原则，不预定义无消费者的接口族）。
"""

from __future__ import annotations

from typing import Protocol


class SystemPromptProvider(Protocol):
    """按功能模式提供系统提示词的端口。"""

    def retrieval_prompt(self, enable_web_search: bool) -> str:
        """知识检索模式的系统提示词。

        ``enable_web_search`` 决定是否包含联网搜索指引分支。
    """

    def direct_prompt(self) -> str:
        """无技能时的普通对话系统提示词。"""
        ...
        ...

    def practice_prompt(self, enable_web_search: bool = False) -> str:
        """模拟练习模式的系统提示词（消费者：``DeepAgentsPracticeWorkflowRunner``）。"""
        ...

    def quiz_generation_prompt(self) -> str:
        """出题工具内部生成题目使用的提示词模板。

        包含 ``{document_context}`` / ``{requirements}`` 占位符，
        由 ``generate_quiz_paper`` 工具填充。
        """
        ...

    def summarization_prompt(self) -> str:
        """会话压缩摘要提示词（``SummarizationMiddleware`` 的 ``summary_prompt``）。

        必须包含 ``{messages}`` 占位符；要求模型输出纯文本要点、禁止章节标题与
        结构化标签，避免压缩摘要格式泄漏到面向用户的回答。
        """
        ...

    def anchor_extraction_prompt(self) -> str:
        """会话锚点提取提示词（``AnchorMemoryMiddleware`` 的 ``extract_prompt``）。

        含 ``{existing_anchors}`` / ``{messages}`` / ``max_chars``（字面量）
        三个待填项；要求模型输出纯文本锚点正文（实体关系 + 背景设定）。
        """
        ...
