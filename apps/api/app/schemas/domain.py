# ==============================================================================
# Domain（领域/科目）Schema 定义
# ==============================================================================
# 功能：
#   - 定义领域/科目相关的所有请求/响应格式
#   - 前后端数据契约
#
# 数据流向：
#   前端请求 → Request Schema → 业务逻辑 → Response Schema → 前端
# ==============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==============================================================================
# Domain 相关 Schema
# ==============================================================================

class DomainCreate(BaseModel):
    """
    创建领域/科目请求

    说明：
        - 创建新的学习领域或科目
        - grade 和 semester 用于按学期分组

    前端调用：
        domainApi.create({
          name: "数据结构",
          code: "CS201",
          description: "计算机科学核心课程",
          grade: "大二",
          semester: "上"
        })
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="领域/科目名称",
    )
    code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="科目编码，如 CS201",
    )
    description: Optional[str] = Field(
        default=None,
        description="科目描述",
    )
    grade: str = Field(
        ...,
        description="年级：大一/大二/大三/大四",
    )
    semester: str = Field(
        ...,
        description="学期：上/下",
    )
    sort_order: int = Field(
        default=0,
        description="排序顺序（越小越靠前）",
    )
    is_active: bool = Field(
        default=True,
        description="是否启用",
    )


class DomainUpdate(BaseModel):
    """
    更新领域/科目请求

    说明：
        - 所有字段均可选，仅更新传入的字段
    """

    name: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="领域/科目名称",
    )
    code: Optional[str] = Field(
        default=None,
        max_length=50,
        description="科目编码",
    )
    description: Optional[str] = Field(
        default=None,
        description="科目描述",
    )
    grade: Optional[str] = Field(
        default=None,
        description="年级：大一/大二/大三/大四",
    )
    semester: Optional[str] = Field(
        default=None,
        description="学期：上/下",
    )
    sort_order: Optional[int] = Field(
        default=None,
        description="排序顺序",
    )
    is_active: Optional[bool] = Field(
        default=None,
        description="是否启用",
    )


class DomainResponse(BaseModel):
    """
    领域/科目响应

    说明：
        - 返回领域/科目完整信息

    响应示例：
        {
          "id": "550e8400-e29b-41d4-a716-446655440000",
          "name": "数据结构",
          "code": "CS201",
          "description": "计算机科学核心课程",
          "grade": "大二",
          "semester": "上",
          "sort_order": 1,
          "is_active": true,
          "created_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="领域/科目 ID")
    name: str = Field(description="领域/科目名称")
    code: Optional[str] = Field(default=None, description="科目编码")
    description: Optional[str] = Field(default=None, description="科目描述")
    grade: str = Field(description="年级")
    semester: str = Field(description="学期")
    sort_order: int = Field(description="排序顺序")
    is_active: bool = Field(description="是否启用")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}
