"""Pydantic contracts for the chat API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ChatSource(BaseModel):
    id: str = Field(description="Referenced source id (knowledge chunk id or web URL)")
    title: str = Field(description="Referenced source title (knowledge chunk title or web page title)")
    document_id: str | None = Field(default=None, description="Source document id for RAG hits, null for web sources")
    score: float | None = Field(default=None, description="Similarity score for RAG hits, null for web sources")
    url: str | None = Field(default=None, description="Web source URL, null for local RAG sources")


class ChatSessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ChatSessionResponse(BaseModel):
    id: str
    title: str
    status: str
    message_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    document_ids: list[str] = Field(
        default_factory=list,
        description="通过 @ 选择的文档 ID 列表（练习模式作为出题上下文）",
    )
    capabilities: list[Literal['knowledge', 'practice', 'web_search']] = Field(
        default_factory=list,
        description='可组合的聊天能力；为空时直接与模型对话。',
    )


class PromptEnhanceRequest(BaseModel):
    content: str = Field(min_length=1, max_length=10000)


class PromptEnhanceResponse(BaseModel):
    content: str


class ChatMessageResponse(BaseModel):
    id: str
    session_id: str
    role: str
    content: str
    sources: list[ChatSource] | None = None
    quiz_paper_id: str | None = Field(
        default=None,
        description="模拟练习消息关联的试卷 ID；普通消息为 null",
    )
    document_ids: list[str] | None = Field(
        default=None,
        description="用户消息通过 @ 选择的文档 ID 列表；普通消息为 null",
    )
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatSessionCapabilitiesUpdate(BaseModel):
    capabilities: list[Literal['knowledge', 'practice', 'web_search']] = Field(
        default_factory=list,
        description="会话默认聊天能力列表；空列表表示清除默认能力",
    )


class ChatSessionDetail(ChatSessionResponse):
    messages: list[ChatMessageResponse] = Field(default_factory=list)
    capabilities: list[Literal['knowledge', 'practice', 'web_search']] = Field(
        default_factory=list,
        description="会话默认聊天能力列表（最近一次消息用到的能力自动同步）",
    )
