# ==============================================================================
# Chapter（章节）Schema 定义
# ==============================================================================
# 功能：
#   - 定义章节相关的所有请求/响应格式
#   - 支持多级章节树结构（章 → 节 → 小节）
#   - 前后端数据契约
#
# 数据流向：
#   前端请求 → Request Schema → 业务逻辑 → Response Schema → 前端
# ==============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==============================================================================
# Chapter 相关 Schema
# ==============================================================================

class ChapterCreate(BaseModel):
    """
    创建章节请求

    说明：
        - 创建章节节点，支持多级嵌套
        - parent_id 为空时为顶级章节
        - level: 1=章, 2=节, 3=小节

    前端调用：
        chapterApi.create({
          domain_id: "550e8400-...",
          name: "第三章 排序算法",
          level: 1,
          sort_order: 3
        })
    """

    domain_id: str = Field(description="所属领域/科目 ID")
    parent_id: Optional[str] = Field(
        default=None,
        description="父章节 ID，NULL 表示顶级章节",
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="章节名称",
    )
    level: int = Field(
        default=1,
        description="章节层级：1=章, 2=节, 3=小节",
    )
    sort_order: int = Field(
        default=0,
        description="排序顺序（越小越靠前）",
    )
    description: Optional[str] = Field(
        default=None,
        description="章节描述",
    )


class ChapterUpdate(BaseModel):
    """
    更新章节请求

    说明：
        - 所有字段均可选，仅更新传入的字段
        - 不支持修改 domain_id 和 parent_id（需重建树结构）
    """

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=200,
        description="章节名称",
    )
    level: Optional[int] = Field(
        default=None,
        description="章节层级：1=章, 2=节, 3=小节",
    )
    sort_order: Optional[int] = Field(
        default=None,
        description="排序顺序",
    )
    description: Optional[str] = Field(
        default=None,
        description="章节描述",
    )


class ChapterResponse(BaseModel):
    """
    章节响应

    说明：
        - 返回章节完整信息
        - children 字段包含子章节列表（嵌套结构）

    响应示例：
        {
          "id": "...",
          "domain_id": "...",
          "parent_id": null,
          "name": "第三章 排序算法",
          "level": 1,
          "sort_order": 3,
          "description": "常见排序算法的原理与实现",
          "created_at": "2026-07-27T10:00:00Z",
          "children": [
            {
              "id": "...",
              "name": "3.1 冒泡排序",
              "level": 2,
              "children": []
            }
          ]
        }
    """

    id: str = Field(description="章节 ID")
    domain_id: str = Field(description="所属领域/科目 ID")
    parent_id: Optional[str] = Field(default=None, description="父章节 ID")
    name: str = Field(description="章节名称")
    level: int = Field(description="章节层级")
    sort_order: int = Field(description="排序顺序")
    description: Optional[str] = Field(default=None, description="章节描述")
    created_at: datetime = Field(description="创建时间")
    children: list["ChapterResponse"] = Field(
        default_factory=list,
        description="子章节列表（嵌套）",
    )

    model_config = {"from_attributes": True}
