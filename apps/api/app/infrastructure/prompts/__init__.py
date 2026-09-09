"""聊天系统提示词：常量唯一出处与提供者实现。

对外只导出稳定实现（``ChatSystemPromptProvider``）；提示词常量不在此导出，
统一经 provider 取用，避免多个导入入口。
"""

from app.infrastructure.prompts.provider import ChatSystemPromptProvider

__all__ = ["ChatSystemPromptProvider"]
