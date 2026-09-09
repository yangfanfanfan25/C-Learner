"""Pydantic contracts for the mock practice (quiz) feature.

试卷 JSON 是 LLM 结构化输出的核心契约：所有生成结果必须通过
``QuizPaper`` 校验后才能落库、导出与判分。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

QuestionType = Literal["choice", "multi_choice", "true_false", "fill", "short_answer"]

_OPTION_TYPES = {"choice", "multi_choice"}
_NO_OPTION_TYPES = {"true_false", "fill", "short_answer"}


class QuizOption(BaseModel):
    """选择题选项。"""

    key: str = Field(description="选项键，如 A/B/C/D")
    text: str = Field(description="选项文本")


class QuizQuestion(BaseModel):
    """单道题目（含答案与解析，是判分与导出的数据源）。"""

    id: str = Field(description="题号，如 q1")
    type: QuestionType = Field(description="题型")
    stem: str = Field(description="题干")
    options: list[QuizOption] = Field(
        default_factory=list,
        description="选择题选项；choice/multi_choice 必填非空，其余题型为空",
    )
    answer: str | list[str] | bool = Field(
        description="参考答案：choice 为选项 key；multi_choice 为 key 列表；"
        "true_false 为布尔；fill/short_answer 为参考答案文本",
    )
    explanation: str = Field(default="", description="解析")
    knowledge_points: list[str] = Field(default_factory=list, description="关联知识点")
    difficulty: int = Field(default=1, ge=1, le=3, description="1=基础 2=进阶 3=综合")

    @model_validator(mode="after")
    def _validate_by_type(self) -> "QuizQuestion":
        if self.type in _OPTION_TYPES:
            if not self.options:
                raise ValueError(f"{self.type} 题型必须提供 options")
            valid_keys = {option.key for option in self.options}
            if self.type == "choice" and self.answer not in valid_keys:
                raise ValueError(f"choice 题答案 {self.answer!r} 不在选项 keys {sorted(valid_keys)} 中")
            if self.type == "multi_choice":
                if not isinstance(self.answer, list):
                    raise ValueError("multi_choice 题 answer 必须为选项 key 列表")
                missing = [key for key in self.answer if key not in valid_keys]
                if missing:
                    raise ValueError(f"multi_choice 题答案包含不存在的选项 key：{missing}")
        elif self.type in _NO_OPTION_TYPES:
            if self.options:
                raise ValueError(f"{self.type} 题型不应提供 options")
            if self.type == "true_false" and not isinstance(self.answer, bool):
                raise ValueError("true_false 题 answer 必须为布尔值")
            if self.type in {"fill", "short_answer"} and not isinstance(self.answer, str):
                raise ValueError(f"{self.type} 题 answer 必须为字符串")
        return self


class QuizPaper(BaseModel):
    """整套模拟练习试卷（LLM 结构化输出的目标结构）。"""

    title: str = Field(description="试卷标题")
    difficulty: int = Field(default=1, ge=1, le=3, description="1=基础 2=进阶 3=综合")
    question_types: list[str] = Field(
        default_factory=list,
        description="实际题型列表（由 questions 推导，LLM 可忽略）",
    )
    total: int = Field(default=0, ge=0, description="题目总数（由 questions 推导，LLM 可忽略）")
    questions: list[QuizQuestion] = Field(min_length=1, description="题目列表")

    @model_validator(mode="after")
    def _sync_derived_fields(self) -> "QuizPaper":
        """total 与 question_types 始终从 questions 推导，避免 LLM 输出不一致。"""
        self.total = len(self.questions)
        self.question_types = list(dict.fromkeys(question.type for question in self.questions))
        return self


class QuizPaperDetailResponse(BaseModel):
    """试卷详情响应（聊天重载与在线答题页共用）。"""

    id: str
    session_id: str | None = None
    title: str
    document_ids: list[str] = Field(default_factory=list)
    document_titles: list[str] = Field(default_factory=list)
    requirements: str | None = None
    difficulty: int = 1
    question_types: list[str] = Field(default_factory=list)
    total: int = 0
    questions: list[QuizQuestion] = Field(default_factory=list)
    downloads: dict[str, str] | None = Field(
        default=None,
        description="下载直链映射：{\"md\": \"/api/quiz/papers/{id}/download?format=md\", \"json\": ...}",
    )
    created_at: datetime


class QuizAnswerInput(BaseModel):
    """单题作答输入。"""

    question_id: str = Field(description="题目 id")
    value: str | list[str] | bool = Field(description="作答内容，与题型对应")


class QuizGradeRequest(BaseModel):
    """判分请求：一次提交整张试卷的作答。"""

    answers: list[QuizAnswerInput] = Field(min_length=1, description="作答列表")


class QuizGradeResultItem(BaseModel):
    """单题判分结果。"""

    question_id: str
    correct: bool | None = Field(
        default=None,
        description="是否答对；short_answer 不自动判分时为 null",
    )
    user_answer: str | list[str] | bool | None = None
    correct_answer: str | list[str] | bool | None = None
    explanation: str = ""


class QuizGradeResponse(BaseModel):
    """判分结果：总分 + 每题对错与解析。"""

    paper_id: str
    total: int
    correct_count: int
    score: int = Field(description="百分制得分")
    results: list[QuizGradeResultItem]
