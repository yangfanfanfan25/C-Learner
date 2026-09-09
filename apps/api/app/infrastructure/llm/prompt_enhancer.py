"""LLM-backed prompt enhancement adapter."""

from __future__ import annotations

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage


class LangChainPromptEnhancer:
    def __init__(self, model: BaseChatModel):
        self.model = model

    async def enhance(self, content: str) -> str:
        response = await self.model.ainvoke(
            [
                SystemMessage(
                    content=(
                        "你是提示词优化助手。请用中文改写用户提示词，保留原意，补充清晰的目标、"
                        "背景、约束和输出格式。只返回改写后的提示词，不要解释改写过程。"
                    )
                ),
                HumanMessage(content=content),
            ]
        )
        value = response.content
        if isinstance(value, str):
            result = value.strip()
        elif isinstance(value, list):
            result = "".join(
                str(item.get("text") or item.get("content") or "")
                for item in value
                if isinstance(item, dict)
            ).strip()
        else:
            result = ""
        if not result:
            raise RuntimeError("模型未返回增强后的提示词")
        return result
