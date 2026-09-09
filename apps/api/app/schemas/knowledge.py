# ==============================================================================
# Knowledge（知识点）Schema 定义
# ==============================================================================
# 功能：
#   - 定义知识点相关的所有请求/响应格式
#   - 包含：知识点目录、知识点内容、知识点链接、知识点来源
#   - 前后端数据契约
#
# 数据流向：
#   前端请求 → Request Schema → 业务逻辑 → Response Schema → 前端
# ==============================================================================

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# ==============================================================================
# KnowledgeCatalog（知识点目录）相关 Schema
# ==============================================================================

class KnowledgeCatalogCreate(BaseModel):
    """
    创建知识点目录请求

    说明：
        - 知识点目录是知识点的索引条目
        - 每个目录归属于一个章节

    前端调用：
        knowledgeApi.createCatalog({
          chapter_id: "550e8400-...",
          title: "快速排序",
          domain: "数据结构",
          chapter: "排序算法",
          section: "交换排序"
        })
    """

    chapter_id: str = Field(description="所属章节 ID")
    title: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="知识点标题",
    )
    domain: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="所属领域/学科",
    )
    chapter: Optional[str] = Field(
        default=None,
        description="所属章",
    )
    section: Optional[str] = Field(
        default=None,
        description="所属节",
    )
    sort_order: int = Field(
        default=0,
        description="排序顺序（越小越靠前）",
    )


class KnowledgeCatalogResponse(BaseModel):
    """
    知识点目录响应

    说明：
        - 返回知识点目录完整信息

    响应示例：
        {
          "id": "...",
          "chapter_id": "...",
          "title": "快速排序",
          "domain": "数据结构",
          "chapter": "排序算法",
          "section": "交换排序",
          "sort_order": 1,
          "created_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="知识点目录 ID")
    chapter_id: str = Field(description="所属章节 ID")
    title: str = Field(description="知识点标题")
    domain: str = Field(description="所属领域/学科")
    chapter: Optional[str] = Field(default=None, description="所属章")
    section: Optional[str] = Field(default=None, description="所属节")
    sort_order: int = Field(description="排序顺序")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# ==============================================================================
# KnowledgeContent（知识点内容）相关 Schema
# ==============================================================================

class KnowledgeContentCreate(BaseModel):
    """
    创建知识点内容请求

    说明：
        - 知识点的详细内容，包含 Markdown 正文、要点、公式、例题
        - 一个 catalog 对应一条 content

    前端调用：
        knowledgeApi.createContent({
          catalog_id: "550e8400-...",
          content: "# 快速排序\\n\\n快速排序是一种...",
          key_points: ["平均时间复杂度 O(nlogn)", "不稳定排序"],
          difficulty_level: 2
        })
    """

    catalog_id: str = Field(description="所属知识点目录 ID")
    content: str = Field(description="知识点内容（Markdown 格式）")
    key_points: Optional[list[str]] = Field(
        default=None,
        description="关键要点列表（JSON 数组）",
    )
    formulas: Optional[list[str]] = Field(
        default=None,
        description="相关公式列表（LaTeX 格式）",
    )
    examples: Optional[list[dict]] = Field(
        default=None,
        description="例题列表，格式: [{question, answer, solution}]",
    )
    difficulty_level: int = Field(
        default=1,
        description="难度等级：1=基础, 2=进阶, 3=综合",
    )
    exam_frequency: int = Field(
        default=0,
        description="考试出现频率（数值越高越常考）",
    )


class KnowledgeContentResponse(BaseModel):
    """
    知识点内容响应

    响应示例：
        {
          "id": "...",
          "catalog_id": "...",
          "content": "# 快速排序\\n\\n...",
          "key_points": ["平均时间复杂度 O(nlogn)"],
          "formulas": ["T(n) = 2T(n/2) + O(n)"],
          "examples": [...],
          "difficulty_level": 2,
          "exam_frequency": 5,
          "created_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="知识点内容 ID")
    catalog_id: str = Field(description="所属知识点目录 ID")
    content: str = Field(description="知识点内容（Markdown）")
    key_points: Optional[list[str]] = Field(default=None, description="关键要点")
    formulas: Optional[list[str]] = Field(default=None, description="相关公式")
    examples: Optional[list[dict]] = Field(default=None, description="例题列表")
    difficulty_level: int = Field(description="难度等级")
    exam_frequency: int = Field(description="考试出现频率")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# ==============================================================================
# KnowledgeLink（知识点链接）相关 Schema
# ==============================================================================

class KnowledgeLinkCreate(BaseModel):
    """
    创建知识点链接请求

    说明：
        - 表示两个知识点之间的关系
        - relation_type 取值：
            prerequisite  - 前置知识
            composable   - 可组合
            similar_to   - 相似
            part_of      - 从属于
            leads_to     - 延伸到
            easily_confused - 易混淆

    前端调用：
        knowledgeApi.createLink({
          source_id: "...",
          target_id: "...",
          relation_type: "prerequisite",
          weight: 0.8,
          context: "学习快速排序前需掌握二分思想"
        })
    """

    source_id: str = Field(description="源知识点 ID")
    target_id: str = Field(description="目标知识点 ID")
    relation_type: str = Field(
        ...,
        description="关系类型：prerequisite/composable/similar_to/part_of/leads_to/easily_confused",
    )
    weight: float = Field(
        default=1.0,
        description="关联权重（0.0 ~ 1.0）",
    )
    context: Optional[str] = Field(
        default=None,
        description="关联说明/上下文",
    )
    is_cross_domain: bool = Field(
        default=False,
        description="是否跨领域关联",
    )


class KnowledgeLinkResponse(BaseModel):
    """
    知识点链接响应

    响应示例：
        {
          "id": "...",
          "source_id": "...",
          "target_id": "...",
          "relation_type": "prerequisite",
          "weight": 0.8,
          "context": "学习快速排序前需掌握二分思想",
          "is_cross_domain": false,
          "created_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="链接 ID")
    source_id: str = Field(description="源知识点 ID")
    target_id: str = Field(description="目标知识点 ID")
    relation_type: str = Field(description="关系类型")
    weight: float = Field(description="关联权重")
    context: Optional[str] = Field(default=None, description="关联说明")
    is_cross_domain: bool = Field(description="是否跨领域关联")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# ==============================================================================
# KnowledgeSource（知识点来源）相关 Schema
# ==============================================================================

class KnowledgeSourceCreate(BaseModel):
    """
    创建知识点来源请求

    说明：
        - 记录知识点的原始来源（PDF、PPT、文档等）
        - 用于溯源和引用

    前端调用：
        knowledgeApi.createSource({
          catalog_id: "...",
          source_type: "pdf",
          source_filename: "数据结构第三章.pdf",
          page_range: "10-15"
        })
    """

    catalog_id: Optional[str] = Field(
        default=None,
        description="关联知识点目录 ID",
    )
    source_type: str = Field(
        ...,
        description="来源类型：pdf/ppt/docx/image",
    )
    source_filename: Optional[str] = Field(
        default=None,
        description="源文件名",
    )
    source_path: Optional[str] = Field(
        default=None,
        description="源文件路径",
    )
    markdown_content: Optional[str] = Field(
        default=None,
        description="提取的 Markdown 内容",
    )
    page_range: Optional[str] = Field(
        default=None,
        description="页码范围，如 10-15",
    )


class KnowledgeSourceResponse(BaseModel):
    """
    知识点来源响应

    响应示例：
        {
          "id": "...",
          "catalog_id": "...",
          "source_type": "pdf",
          "source_filename": "数据结构第三章.pdf",
          "source_path": "/uploads/...",
          "markdown_content": "...",
          "page_range": "10-15",
          "extracted_at": "2026-07-27T10:00:00Z",
          "created_at": "2026-07-27T10:00:00Z"
        }
    """

    id: str = Field(description="来源 ID")
    catalog_id: Optional[str] = Field(default=None, description="关联知识点目录 ID")
    source_type: str = Field(description="来源类型")
    source_filename: Optional[str] = Field(default=None, description="源文件名")
    source_path: Optional[str] = Field(default=None, description="源文件路径")
    markdown_content: Optional[str] = Field(default=None, description="提取的 Markdown 内容")
    page_range: Optional[str] = Field(default=None, description="页码范围")
    extracted_at: Optional[datetime] = Field(default=None, description="提取时间")
    created_at: datetime = Field(description="创建时间")

    model_config = {"from_attributes": True}


# ==============================================================================
# 组合响应 Schema
# ==============================================================================

class KnowledgeDetailResponse(BaseModel):
    """
    知识点详情响应（组合视图）

    说明：
        - 聚合 catalog + content + links + sources
        - 用于知识点详情页一次性返回所有关联数据
    """

    catalog: KnowledgeCatalogResponse = Field(description="知识点目录信息")
    content: Optional[KnowledgeContentResponse] = Field(
        default=None,
        description="知识点内容（可能尚未生成）",
    )
    links: list[KnowledgeLinkResponse] = Field(
        default_factory=list,
        description="关联的知识点链接列表",
    )
    sources: list[KnowledgeSourceResponse] = Field(
        default_factory=list,
        description="知识点来源列表",
    )
