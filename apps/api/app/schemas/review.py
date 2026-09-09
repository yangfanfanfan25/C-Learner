# ==============================================================================
# ReviewRecord（复习记录）Schema 定义
# ==============================================================================
# 功能：
#   - 定义复习记录相关的所有请求/响应格式
#   - 基于间隔重复算法（Spaced Repetition）管理复习计划
#   - 前后端数据契约
#
# 数据流向：
#   前端请求 → Request Schema → 业务逻辑 → Response Schema → 前端
# ==============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==============================================================================
# ReviewRecord 相关 Schema
# ==============================================================================

class ReviewRecordCreate(BaseModel):
    """
    创建复习记录请求

    说明：
        - 为指定知识点创建复习追踪记录
        - 首次复习时 review_count=1, mastery_level=0

    前端调用：
        reviewApi.createRecord({
          catalog_id: "550e8400-...",
          notes: "需要重点复习二分查找的边界条件"
        })
    """

    catalog_id: str = Field(description="关联知识点目录 ID")
    notes: Optional[str] = Field(
        default=None,
        description="学习笔记/备注",
    )


class ReviewRecordUpdate(BaseModel):
    """
    更新复习记录请求

    说明：
        - 每次复习后更新掌握程度和错误次数
        - 系统根据 mastery_level 自动计算 next_review_at
    """

    mastery_level: Optional[int] = Field(
        default=None,
        description="掌握程度：0=未学习, 1=初见, 2=了解, 3=熟悉, 4=掌握, 5=精通",
    )
    notes: Optional[str] = Field(
        default=None,
        description="学习笔记/备注",
    )
    incorrect_count: Optional[int] = Field(
        default=None,
        description="错误次数（累计）",
    )


class ReviewRecordResponse(BaseModel):
    """
    复习记录响应

    响应示例：
        {
          "id": "...",
          "catalog_id": "...",
          "review_count": 3,
          "last_reviewed_at": "2026-07-27T10:00:00Z",
          "next_review_at": "2026-07-30T10:00:00Z",
          "mastery_level": 3,
          "incorrect_count": 1,
          "notes": "需要重点复习二分查找的边界条件",
          "created_at": "2026-07-20T10:00:00Z",
          "updated_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="复习记录 ID")
    catalog_id: str = Field(description="关联知识点目录 ID")
    review_count: int = Field(description="累计复习次数")
    last_reviewed_at: Optional[datetime] = Field(
        default=None,
        description="上次复习时间",
    )
    next_review_at: Optional[datetime] = Field(
        default=None,
        description="下次复习时间（由间隔重复算法计算）",
    )
    mastery_level: int = Field(description="掌握程度（0-5）")
    incorrect_count: int = Field(description="累计错误次数")
    notes: Optional[str] = Field(default=None, description="学习笔记")
    created_at: datetime = Field(description="创建时间")
    updated_at: datetime = Field(description="更新时间")

    model_config = {"from_attributes": True}
