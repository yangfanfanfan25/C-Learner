# ==============================================================================
# 基础 Schema 定义
# ==============================================================================
# 功能：
#   - 定义通用响应格式
#   - 定义分页参数
#   - 提供基础字段
#
# 使用场景：
#   - 所有 API 响应统一格式
#   - 列表查询分页
# ==============================================================================

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field

# 泛型类型变量
T = TypeVar("T")


# ==============================================================================
# 通用响应格式
# ==============================================================================
# 说明：
#   所有 API 响应必须遵循此格式
#   {
#     "code": 200,
#     "message": "success",
#     "data": { ... }
#   }
# ==============================================================================
class APIResponse(BaseModel, Generic[T]):
    """
    通用 API 响应格式

    属性：
        success: 请求是否成功（true/false）
        code: 状态码（200 成功，4xx 客户端错误，5xx 服务端错误）
        message: 响应消息
        data: 响应数据（类型由泛型决定）

    使用示例：
        return APIResponse(code=200, message="success", data={"id": "123"})
    """

    success: bool = Field(default=True, description="请求是否成功")
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")


# ==============================================================================
# 分页参数
# ==============================================================================
# 说明：
#   列表查询时的分页参数
#   page: 页码（从 1 开始）
#   page_size: 每页数量（默认 20，最大 100）
# ==============================================================================
class PaginationParams(BaseModel):
    """
    分页参数

    使用方式：
        @router.get("/items")
        def list_items(page: int = 1, page_size: int = 20):
            pagination = PaginationParams(page=page, page_size=page_size)
    """

    page: int = Field(default=1, ge=1, description="页码（从 1 开始）")
    page_size: int = Field(default=20, ge=1, le=100, description="每页数量")

    @property
    def offset(self) -> int:
        """计算偏移量"""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """获取限制数量"""
        return self.page_size


# ==============================================================================
# 分页响应
# ==============================================================================
# 说明：
#   列表查询的响应格式
#   {
#     "items": [...],
#     "total": 100,
#     "page": 1,
#     "page_size": 20,
#     "total_pages": 5
#   }
# ==============================================================================
class PaginatedData(BaseModel, Generic[T]):
    """
    分页数据

    属性：
        items: 数据列表
        total: 总数量
        page: 当前页码
        page_size: 每页数量
        total_pages: 总页数
    """

    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(description="总数量")
    page: int = Field(description="当前页码")
    page_size: int = Field(description="每页数量")
    total_pages: int = Field(description="总页数")
