# ==============================================================================
# Knowledge API 路由
# ==============================================================================
# 功能：
#   - 定义知识点体系的所有 CRUD API 端点
#   - 包含：知识点目录、知识点内容、知识点链接、知识点来源
#   - 删除知识点目录时级联删除 content + links + sources + review
#
# 数据流向：
#   前端请求 → API 路由 → 数据库 → 响应
#
# API 端点：
#   POST   /knowledge/catalog           创建知识点目录
#   GET    /knowledge/catalog           获取知识点列表（支持按domain/chapter_id筛选，分页）
#   GET    /knowledge/catalog/{id}      获取知识点详情（含content+links+sources）
#   PUT    /knowledge/catalog/{id}      更新知识点目录
#   DELETE /knowledge/catalog/{id}      删除知识点（级联删除content+links+sources+review）
#
#   POST   /knowledge/content           创建知识点内容
#   GET    /knowledge/content/{catalog_id}  获取知识点内容
#   PUT    /knowledge/content/{catalog_id}  更新知识点内容
#
#   POST   /knowledge/links             创建知识点链接
#   GET    /knowledge/links/{catalog_id}    获取知识点的所有链接
#   DELETE /knowledge/links/{id}        删除链接
#
#   POST   /knowledge/sources           创建知识点来源
#   GET    /knowledge/sources/{catalog_id}  获取知识点的所有来源
#   DELETE /knowledge/sources/{id}      删除来源
# ==============================================================================

import json
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.sqlite.engine import get_db
from app.infrastructure.knowledge_models import (
    KnowledgeCatalog,
    KnowledgeContent,
    KnowledgeLink,
    KnowledgeSource,
)
from app.schemas.base import APIResponse, PaginatedData
from app.schemas.knowledge import (
    KnowledgeCatalogCreate,
    KnowledgeCatalogResponse,
    KnowledgeContentCreate,
    KnowledgeContentResponse,
    KnowledgeLinkCreate,
    KnowledgeLinkResponse,
    KnowledgeSourceCreate,
    KnowledgeSourceResponse,
    KnowledgeDetailResponse,
)

# 创建路由器
router = APIRouter(prefix="/knowledge", tags=["Knowledge"])


# ==============================================================================
# 知识点目录端点
# ==============================================================================

@router.post(
    "/catalog",
    response_model=APIResponse[KnowledgeCatalogResponse],
    summary="创建知识点目录",
    description="创建新的知识点目录条目",
)
def create_catalog(
    body: KnowledgeCatalogCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeCatalogResponse]:
    """
    创建知识点目录

    请求体：
        {
          "chapter_id": "550e8400-...",
          "title": "快速排序",
          "domain": "数据结构",
          "chapter": "排序算法",
          "section": "交换排序",
          "sort_order": 1
        }
    """
    catalog = KnowledgeCatalog(
        chapter_id=body.chapter_id,
        title=body.title,
        domain=body.domain,
        chapter=body.chapter,
        section=body.section,
        sort_order=body.sort_order,
    )
    db.add(catalog)
    db.commit()
    db.refresh(catalog)

    return APIResponse(
        code=200,
        message="知识点目录创建成功",
        data=KnowledgeCatalogResponse.model_validate(catalog),
    )


@router.get(
    "/catalog",
    response_model=APIResponse[PaginatedData[KnowledgeCatalogResponse]],
    summary="获取知识点列表",
    description="分页获取知识点列表，支持按 domain 和 chapter_id 筛选",
)
def list_catalogs(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    domain: Optional[str] = Query(None, description="按领域筛选"),
    chapter_id: Optional[str] = Query(None, description="按章节 ID 筛选"),
    db: Session = Depends(get_db),
) -> APIResponse[PaginatedData[KnowledgeCatalogResponse]]:
    """获取知识点列表"""
    query = db.query(KnowledgeCatalog)

    # 筛选条件
    if domain:
        query = query.filter(KnowledgeCatalog.domain == domain)
    if chapter_id:
        query = query.filter(KnowledgeCatalog.chapter_id == chapter_id)

    # 查询总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    catalogs = (
        query
        .order_by(KnowledgeCatalog.sort_order.asc(), KnowledgeCatalog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return APIResponse(
        code=200,
        message="success",
        data=PaginatedData(
            items=[KnowledgeCatalogResponse.model_validate(c) for c in catalogs],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/catalog/{catalog_id}",
    response_model=APIResponse[KnowledgeDetailResponse],
    summary="获取知识点详情",
    description="根据 ID 获取知识点详情（含 content + links + sources）",
)
def get_catalog(
    catalog_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeDetailResponse]:
    """获取知识点详情（含 content + links + sources）"""
    catalog = db.query(KnowledgeCatalog).filter(KnowledgeCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 获取关联数据
    content = db.query(KnowledgeContent).filter(KnowledgeContent.catalog_id == catalog_id).first()
    outgoing_links = db.query(KnowledgeLink).filter(KnowledgeLink.source_id == catalog_id).all()
    sources = db.query(KnowledgeSource).filter(KnowledgeSource.catalog_id == catalog_id).all()

    resp = KnowledgeDetailResponse(
        catalog=KnowledgeCatalogResponse.model_validate(catalog),
        content=KnowledgeContentResponse.model_validate(content) if content else None,
        links=[KnowledgeLinkResponse.model_validate(link) for link in outgoing_links],
        sources=[KnowledgeSourceResponse.model_validate(s) for s in sources],
    )

    return APIResponse(code=200, message="success", data=resp)


@router.put(
    "/catalog/{catalog_id}",
    response_model=APIResponse[KnowledgeCatalogResponse],
    summary="更新知识点目录",
    description="更新知识点目录信息",
)
def update_catalog(
    catalog_id: str,
    body: KnowledgeCatalogCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeCatalogResponse]:
    """更新知识点目录"""
    catalog = db.query(KnowledgeCatalog).filter(KnowledgeCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 更新字段
    catalog.title = body.title
    catalog.chapter_id = body.chapter_id
    catalog.domain = body.domain
    catalog.chapter = body.chapter
    catalog.section = body.section
    catalog.sort_order = body.sort_order

    db.commit()
    db.refresh(catalog)

    return APIResponse(
        code=200,
        message="知识点目录更新成功",
        data=KnowledgeCatalogResponse.model_validate(catalog),
    )


@router.delete(
    "/catalog/{catalog_id}",
    response_model=APIResponse[bool],
    summary="删除知识点",
    description="删除知识点及其关联的所有 content、links、sources、review 记录（级联删除）",
)
def delete_catalog(
    catalog_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除知识点（级联删除 content + links + sources + review）"""
    catalog = db.query(KnowledgeCatalog).filter(KnowledgeCatalog.id == catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=404, detail="知识点不存在")

    # 级联删除（SQLAlchemy relationship 已配置 cascade）
    db.delete(catalog)
    db.commit()

    return APIResponse(code=200, message="删除成功", data=True)


# ==============================================================================
# 知识点内容端点
# ==============================================================================

@router.post(
    "/content",
    response_model=APIResponse[KnowledgeContentResponse],
    summary="创建知识点内容",
    description="为知识点创建详细内容（Markdown 正文、要点、公式、例题）",
)
def create_content(
    body: KnowledgeContentCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeContentResponse]:
    """
    创建知识点内容

    请求体：
        {
          "catalog_id": "550e8400-...",
          "content": "# 快速排序\n\n快速排序是一种...",
          "key_points": ["平均时间复杂度 O(nlogn)", "不稳定排序"],
          "difficulty_level": 2
        }
    """
    # 验证 catalog 是否存在
    catalog = db.query(KnowledgeCatalog).filter(KnowledgeCatalog.id == body.catalog_id).first()
    if not catalog:
        raise HTTPException(status_code=400, detail="知识点目录不存在")

    # 检查是否已存在 content（一对一关系）
    existing = db.query(KnowledgeContent).filter(KnowledgeContent.catalog_id == body.catalog_id).first()
    if existing:
        raise HTTPException(status_code=400, detail="该知识点已有内容，请使用更新接口")

    # 将 list 字段序列化为 JSON 字符串存储
    content = KnowledgeContent(
        catalog_id=body.catalog_id,
        content=body.content,
        key_points=json.dumps(body.key_points, ensure_ascii=False) if body.key_points else None,
        formulas=json.dumps(body.formulas, ensure_ascii=False) if body.formulas else None,
        examples=json.dumps(body.examples, ensure_ascii=False) if body.examples else None,
        difficulty_level=body.difficulty_level,
        exam_frequency=body.exam_frequency,
    )
    db.add(content)
    db.commit()
    db.refresh(content)

    return APIResponse(
        code=200,
        message="知识点内容创建成功",
        data=_build_content_response(content),
    )


@router.get(
    "/content/{catalog_id}",
    response_model=APIResponse[KnowledgeContentResponse],
    summary="获取知识点内容",
    description="根据 catalog_id 获取知识点内容",
)
def get_content(
    catalog_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeContentResponse]:
    """获取知识点内容"""
    content = db.query(KnowledgeContent).filter(KnowledgeContent.catalog_id == catalog_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="知识点内容不存在")

    return APIResponse(
        code=200,
        message="success",
        data=_build_content_response(content),
    )


@router.put(
    "/content/{catalog_id}",
    response_model=APIResponse[KnowledgeContentResponse],
    summary="更新知识点内容",
    description="更新知识点的详细内容",
)
def update_content(
    catalog_id: str,
    body: KnowledgeContentCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeContentResponse]:
    """更新知识点内容"""
    content = db.query(KnowledgeContent).filter(KnowledgeContent.catalog_id == catalog_id).first()
    if not content:
        raise HTTPException(status_code=404, detail="知识点内容不存在")

    # 更新字段
    content.content = body.content
    content.key_points = json.dumps(body.key_points, ensure_ascii=False) if body.key_points else None
    content.formulas = json.dumps(body.formulas, ensure_ascii=False) if body.formulas else None
    content.examples = json.dumps(body.examples, ensure_ascii=False) if body.examples else None
    content.difficulty_level = body.difficulty_level
    content.exam_frequency = body.exam_frequency

    db.commit()
    db.refresh(content)

    return APIResponse(
        code=200,
        message="知识点内容更新成功",
        data=_build_content_response(content),
    )


def _build_content_response(content: KnowledgeContent) -> KnowledgeContentResponse:
    """构建知识点内容响应（处理 JSON 字段反序列化）"""
    return KnowledgeContentResponse(
        id=content.id,
        catalog_id=content.catalog_id,
        content=content.content,
        key_points=json.loads(content.key_points) if content.key_points else None,
        formulas=json.loads(content.formulas) if content.formulas else None,
        examples=json.loads(content.examples) if content.examples else None,
        difficulty_level=content.difficulty_level,
        exam_frequency=content.exam_frequency,
        created_at=content.created_at,
    )


# ==============================================================================
# 知识点链接端点
# ==============================================================================

@router.post(
    "/links",
    response_model=APIResponse[KnowledgeLinkResponse],
    summary="创建知识点链接",
    description="创建两个知识点之间的关联关系",
)
def create_link(
    body: KnowledgeLinkCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeLinkResponse]:
    """
    创建知识点链接

    请求体：
        {
          "source_id": "...",
          "target_id": "...",
          "relation_type": "prerequisite",
          "weight": 0.8,
          "context": "学习快速排序前需掌握二分思想",
          "is_cross_domain": false
        }
    """
    # 验证源知识点和目标知识点是否存在
    source = db.query(KnowledgeCatalog).filter(KnowledgeCatalog.id == body.source_id).first()
    if not source:
        raise HTTPException(status_code=400, detail="源知识点不存在")
    target = db.query(KnowledgeCatalog).filter(KnowledgeCatalog.id == body.target_id).first()
    if not target:
        raise HTTPException(status_code=400, detail="目标知识点不存在")

    # 检查是否已存在相同链接
    existing = (
        db.query(KnowledgeLink)
        .filter(
            KnowledgeLink.source_id == body.source_id,
            KnowledgeLink.target_id == body.target_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="该链接已存在")

    link = KnowledgeLink(
        source_id=body.source_id,
        target_id=body.target_id,
        relation_type=body.relation_type,
        weight=body.weight,
        context=body.context,
        is_cross_domain=body.is_cross_domain,
    )
    db.add(link)
    db.commit()
    db.refresh(link)

    return APIResponse(
        code=200,
        message="知识点链接创建成功",
        data=KnowledgeLinkResponse.model_validate(link),
    )


@router.get(
    "/links/{catalog_id}",
    response_model=APIResponse[list[KnowledgeLinkResponse]],
    summary="获取知识点链接",
    description="获取指定知识点的所有出向链接",
)
def list_links(
    catalog_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[list[KnowledgeLinkResponse]]:
    """获取知识点的所有链接"""
    links = db.query(KnowledgeLink).filter(KnowledgeLink.source_id == catalog_id).all()

    return APIResponse(
        code=200,
        message="success",
        data=[KnowledgeLinkResponse.model_validate(link) for link in links],
    )


@router.delete(
    "/links/{link_id}",
    response_model=APIResponse[bool],
    summary="删除知识点链接",
    description="删除指定的知识点链接",
)
def delete_link(
    link_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除知识点链接"""
    link = db.query(KnowledgeLink).filter(KnowledgeLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="链接不存在")

    db.delete(link)
    db.commit()

    return APIResponse(code=200, message="链接删除成功", data=True)


# ==============================================================================
# 知识点来源端点
# ==============================================================================

@router.post(
    "/sources",
    response_model=APIResponse[KnowledgeSourceResponse],
    summary="创建知识点来源",
    description="记录知识点的原始文档来源",
)
def create_source(
    body: KnowledgeSourceCreate,
    db: Session = Depends(get_db),
) -> APIResponse[KnowledgeSourceResponse]:
    """
    创建知识点来源

    请求体：
        {
          "catalog_id": "...",
          "source_type": "pdf",
          "source_filename": "数据结构第三章.pdf",
          "source_path": "/uploads/...",
          "markdown_content": "...",
          "page_range": "10-15"
        }
    """
    source = KnowledgeSource(
        catalog_id=body.catalog_id,
        source_type=body.source_type,
        source_filename=body.source_filename,
        source_path=body.source_path,
        markdown_content=body.markdown_content,
        page_range=body.page_range,
    )
    db.add(source)
    db.commit()
    db.refresh(source)

    return APIResponse(
        code=200,
        message="知识点来源创建成功",
        data=KnowledgeSourceResponse.model_validate(source),
    )


@router.get(
    "/sources/{catalog_id}",
    response_model=APIResponse[list[KnowledgeSourceResponse]],
    summary="获取知识点来源",
    description="获取指定知识点的所有来源记录",
)
def list_sources(
    catalog_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[list[KnowledgeSourceResponse]]:
    """获取知识点的所有来源"""
    sources = db.query(KnowledgeSource).filter(KnowledgeSource.catalog_id == catalog_id).all()

    return APIResponse(
        code=200,
        message="success",
        data=[KnowledgeSourceResponse.model_validate(s) for s in sources],
    )


@router.delete(
    "/sources/{source_id}",
    response_model=APIResponse[bool],
    summary="删除知识点来源",
    description="删除指定的知识点来源记录",
)
def delete_source(
    source_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除知识点来源"""
    source = db.query(KnowledgeSource).filter(KnowledgeSource.id == source_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="来源记录不存在")

    db.delete(source)
    db.commit()

    return APIResponse(code=200, message="来源删除成功", data=True)
