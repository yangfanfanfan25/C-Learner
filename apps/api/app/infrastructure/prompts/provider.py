"""聊天系统提示词提供者。

提示词文本全部来自 ``chat_prompts.py``（唯一出处），本模块只负责按模式组装。
无状态、无外部依赖，可作共享单例注入到各运行器。
"""

from __future__ import annotations

from app.infrastructure.prompts.chat_prompts import (
    ANCHOR_EXTRACTION_PROMPT,
    PRACTICE_PROMPT,
    QUIZ_GENERATION_PROMPT,
    RETRIEVAL_PROMPT_FOOTER,
    RETRIEVAL_PROMPT_HEADER,
    RETRIEVAL_PROMPT_WEB_DISABLED,
    RETRIEVAL_PROMPT_WEB_ENABLED,
    SUMMARIZATION_PROMPT,
)


class ChatSystemPromptProvider:
    def direct_prompt(self) -> str:
        return "你是一个中文助手。请直接根据对话上下文回答用户问题，不调用任何工具。"

    """集中提供聊天各功能模式的系统提示词。"""

    def retrieval_prompt(self, enable_web_search: bool) -> str:
        prompt = RETRIEVAL_PROMPT_HEADER
        prompt += (
            RETRIEVAL_PROMPT_WEB_ENABLED
            if enable_web_search
            else RETRIEVAL_PROMPT_WEB_DISABLED
        )
        prompt += RETRIEVAL_PROMPT_FOOTER
        return prompt

    def practice_prompt(self, enable_web_search: bool = False) -> str:
        if not enable_web_search:
            return PRACTICE_PROMPT
        return PRACTICE_PROMPT + (
            "4. 用户同时开启联网搜索时，必须先根据 @ 资料和用户要求提炼适合的搜索词，调用 search_web 获取最新补充信息，"
            "再结合资料内容生成试卷；联网结果只作为补充，不得替代 @ 资料。\n"
        )

    def quiz_generation_prompt(self) -> str:
        return QUIZ_GENERATION_PROMPT

    def summarization_prompt(self) -> str:
        return SUMMARIZATION_PROMPT

    def anchor_extraction_prompt(self) -> str:
        """会话锚点提取提示词（``AnchorMemoryMiddleware`` 的 ``extract_prompt``）。

        含 ``{existing_anchors}`` / ``{messages}`` / ``max_chars``（字面量）
        三个待填项；要求模型输出纯文本锚点正文。
        """
        return ANCHOR_EXTRACTION_PROMPT
