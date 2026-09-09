"""长期记忆数据契约（逐层增补；Phase 1 定义 L0）。"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MemoryActivity(str, Enum):
    conversation = "conversation"
    knowledge = "knowledge"
    practice = "practice"


class L0Context(BaseModel):
    """可验证的本轮学习上下文；未知字段保持为空，不由提取器猜测。"""

    activity: MemoryActivity = MemoryActivity.conversation
    subject: str | None = None
    capabilities: list[str] = Field(default_factory=list)
    document_ids: list[str] = Field(default_factory=list)
    quiz_paper_id: str | None = None


class L0Message(BaseModel):
    """L0 原始会话层的一条消息（清洗后落库的通用形态）。"""

    model_config = ConfigDict(from_attributes=True)

    session_id: str
    user_id: str
    agent_id: str
    recorded_at_ms: int
    id: str
    role: Literal["user", "assistant"]
    content: str
    context: L0Context = Field(default_factory=L0Context)

    @model_validator(mode="before")
    @classmethod
    def normalize_context(cls, values):
        if isinstance(values, dict) and values.get("context") is None:
            values["context"] = L0Context()
        return values


class MemoryType(str, Enum):
    persona = "persona"
    episodic = "episodic"
    instruction = "instruction"


class MemoryAtom(BaseModel):
    """L1 情境记忆：一次具体活动中的偏好、事实或约束。"""

    id: str
    session_id: str
    content: str
    type: MemoryType
    priority: int
    source_message_ids: list[str]
    scene_name: str | None = None
    activity: MemoryActivity = MemoryActivity.conversation
    subject: str | None = None
    scope: Literal["activity", "subject"] = "activity"
    metadata: dict = Field(default_factory=dict)
    timestamps: list[int] = Field(default_factory=list)
    version: int = 1
    created_at_ms: int
    updated_at_ms: int


class L1ExtractionResult(BaseModel):
    """LLM 结构化提取输出。"""

    scene_name: str
    message_ids: list[str]
    memories: list[MemoryAtom]


class DedupAction(str, Enum):
    store = "store"
    skip = "skip"
    update = "update"
    merge = "merge"


class DedupDecision(BaseModel):
    """单条去重判定：store/skip/update/merge + 目标/合并结果。"""

    action: DedupAction
    memory: MemoryAtom
    target_ids: list[str] = Field(default_factory=list)
    merged_content: str | None = None
    merged_priority: int | None = None
    merged_timestamps: list[int] = Field(default_factory=list)


class SceneBlockMeta(BaseModel):
    """L2 策略经验块元信息（scene_index.json 的条目）。"""

    filename: str
    summary: str
    heat: int
    updated_at_ms: int
    activity: MemoryActivity | None = None
    subject: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence_count: int = Field(default=0, ge=0)


class SceneIndex(BaseModel):
    scenes: list[SceneBlockMeta] = Field(default_factory=list)


class SceneExtractOutcome(BaseModel):
    """L2 场景抽取结果。"""

    changed_scenes: list[str] = Field(default_factory=list)
    persona_update_requested: bool = False


class Persona(BaseModel):
    """L3 用户画像（正文 + 场景导航尾段由后处理维护）。"""

    content: str
    updated_at_ms: int


class RecallContext(BaseModel):
    """召回注入载荷。"""

    persona: str | None = None
    scene_navigation: str | None = None
    relevant_strategies: list[str] = Field(default_factory=list)
    relevant_memories: list[MemoryAtom] = Field(default_factory=list)


class AnchorFact(BaseModel):
    """短期会话锚点中的可验证事实。"""

    subject: str = Field(min_length=1)
    attribute: str = Field(min_length=1)
    value: str = Field(min_length=1)
    time: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class AnchorExtractionResult(BaseModel):
    """锚点模型返回的事实增量。"""

    facts: list[AnchorFact] = Field(default_factory=list)
