# ==============================================================================
# Chapter API 路由
# ==============================================================================
# 功能：
#   - 定义章节的所有 CRUD API 端点
#   - 支持多层级章节树结构（章→节→小节）
#   - 支持按 domain_id 筛选，返回树形结构
#   - 删除时级联删除子章节和知识点
#
# 数据流向：
#   前端请求 → API 路由 → 数据库 → 响应
#
# API 端点：
#   POST   /chapters           创建章节
#   GET    /chapters           获取章节列表（支持按domain_id筛选，返回树形结构）
#   GET    /chapters/{id}      获取章节详情（含子章节）
#   PUT    /chapters/{id}      更新章节
#   DELETE /chapters/{id}      删除章节（级联删除子章节和知识点）
# ==============================================================================

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.infrastructure.sqlite.engine import get_db
from app.infrastructure.chapter import Chapter
from app.schemas.base import APIResponse
from app.schemas.chapter import (
    ChapterCreate,
    ChapterUpdate,
    ChapterResponse,
)

# 创建路由器
router = APIRouter(prefix="/chapters", tags=["Chapters"])


# ==============================================================================
# 辅助函数
# ==============================================================================

def _build_chapter_tree(chapters: list[Chapter], parent_id: Optional[str] = None) -> list[ChapterResponse]:
    """
    构建章节树形结构

    说明：
        - 递归构建多级章节树
        - parent_id 为 None 时获取顶层章节
    """
    tree = []
    for chapter in chapters:
        if chapter.parent_id == parent_id:
            resp = ChapterResponse.model_validate(chapter)
            resp.children = _build_chapter_tree(chapters, chapter.id)
            tree.append(resp)
    # 按 sort_order 排序
    tree.sort(key=lambda x: x.sort_order)
    return tree


# ==============================================================================
# 章节 CRUD 端点
# ==============================================================================

@router.post(
    "",
    response_model=APIResponse[ChapterResponse],
    summary="创建章节",
    description="创建新的章节节点，支持多级嵌套",
)
def create_chapter(
    body: ChapterCreate,
    db: Session = Depends(get_db),
) -> APIResponse[ChapterResponse]:
    """
    创建章节

    请求体：
        {
          "domain_id": "550e8400-...",
          "parent_id": null,
          "name": "第三章 排序算法",
          "level": 1,
          "sort_order": 3,
          "description": "常见排序算法的原理与实现"
        }
    """
    # 验证父章节是否存在（如果指定了 parent_id）
    if body.parent_id:
        parent = db.query(Chapter).filter(Chapter.id == body.parent_id).first()
        if not parent:
            raise HTTPException(status_code=400, detail="父章节不存在")

    chapter = Chapter(
        domain_id=body.domain_id,
        parent_id=body.parent_id,
        name=body.name,
        level=body.level,
        sort_order=body.sort_order,
        description=body.description,
    )
    db.add(chapter)
    db.commit()
    db.refresh(chapter)

    resp = ChapterResponse.model_validate(chapter)
    resp.children = []

    return APIResponse(code=200, message="章节创建成功", data=resp)


@router.get(
    "",
    response_model=APIResponse[list[ChapterResponse]],
    summary="获取章节列表",
    description="获取章节树形结构，支持按 domain_id 筛选",
)
def list_chapters(
    domain_id: Optional[str] = Query(None, description="按领域/科目 ID 筛选"),
    db: Session = Depends(get_db),
) -> APIResponse[list[ChapterResponse]]:
    """获取章节列表（树形结构）"""
    query = db.query(Chapter)

    if domain_id:
        query = query.filter(Chapter.domain_id == domain_id)

    # 获取所有匹配的章节，然后构建树形结构
    all_chapters = query.order_by(Chapter.sort_order.asc()).all()
    tree = _build_chapter_tree(all_chapters, parent_id=None)

    return APIResponse(code=200, message="success", data=tree)


@router.get(
    "/{chapter_id}",
    response_model=APIResponse[ChapterResponse],
    summary="获取章节详情",
    description="根据 ID 获取章节详情（含子章节）",
)
def get_chapter(
    chapter_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ChapterResponse]:
    """获取章节详情（含子章节）"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 获取子章节
    children = (
        db.query(Chapter)
        .filter(Chapter.parent_id == chapter_id)
        .order_by(Chapter.sort_order.asc())
        .all()
    )

    resp = ChapterResponse.model_validate(chapter)
    resp.children = [ChapterResponse.model_validate(c) for c in children]

    return APIResponse(code=200, message="success", data=resp)


@router.put(
    "/{chapter_id}",
    response_model=APIResponse[ChapterResponse],
    summary="更新章节",
    description="更新章节信息",
)
def update_chapter(
    chapter_id: str,
    body: ChapterUpdate,
    db: Session = Depends(get_db),
) -> APIResponse[ChapterResponse]:
    """更新章节"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 仅更新传入的非空字段
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chapter, field, value)

    db.commit()
    db.refresh(chapter)

    resp = ChapterResponse.model_validate(chapter)
    resp.children = []

    return APIResponse(code=200, message="章节更新成功", data=resp)


@router.delete(
    "/{chapter_id}",
    response_model=APIResponse[bool],
    summary="删除章节",
    description="删除章节及其关联的所有子章节和知识点（级联删除）",
)
def delete_chapter(
    chapter_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除章节（级联删除子章节和知识点）"""
    chapter = db.query(Chapter).filter(Chapter.id == chapter_id).first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    # 级联删除（SQLAlchemy relationship 已配置 cascade）
    db.delete(chapter)
    db.commit()

    return APIResponse(code=200, message="删除成功", data=True)
