# ==============================================================================
# ExamRecord（出题记录）Schema 定义
# ==============================================================================
# 功能：
#   - 定义出题记录相关的所有请求/响应格式
#   - 记录基于知识点组合生成的题目
#   - 前后端数据契约
#
# 数据流向：
#   前端请求 → Request Schema → 业务逻辑 → Response Schema → 前端
# ==============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==============================================================================
# ExamRecord 相关 Schema
# ==============================================================================

class ExamRecordCreate(BaseModel):
    """
    创建出题记录请求

    说明：
        - 基于选定的知识点组合生成题目
        - knowledge_combo 为知识点 ID 列表
        - 支持指定难度和题型

    前端调用：
        examApi.createRecord({
          knowledge_combo: ["id1", "id2"],
          difficulty: 2,
          question_type: "choice",
          domain: "数据结构"
        })
    """

    knowledge_combo: list[str] = Field(
        ...,
        min_length=1,
        description="知识点 ID 列表（组合出题）",
    )
    difficulty: int = Field(
        ...,
        description="难度等级：1=基础, 2=进阶, 3=综合",
    )
    question_type: Optional[str] = Field(
        default=None,
        description="题型：choice/fill/solve",
    )
    domain: Optional[str] = Field(
        default=None,
        description="所属领域/学科",
    )


class ExamRecordResponse(BaseModel):
    """
    出题记录响应

    响应示例：
        {
          "id": "...",
          "knowledge_combo": ["id1", "id2"],
          "difficulty": 2,
          "question_type": "choice",
          "question_text": "以下哪种排序算法是稳定的？",
          "answer_text": "B. 归并排序",
          "domain": "数据结构",
          "is_used": true,
          "created_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="出题记录 ID")
    knowledge_combo: list[str] = Field(description="知识点 ID 列表")
    difficulty: int = Field(description="难度等级")
    question_type: Optional[str] = Field(default=None, description="题型")
    question_text: Optional[str] = Field(default=None, description="题目内容")
    answer_text: Optional[str] = Field(default=None, description="答案内容")
    domain: Optional[str] = Field(default=None, description="所属领域/学科")
    is_used: bool = Field(description="是否已被使用（已推送给用户）")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
