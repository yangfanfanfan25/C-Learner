# ==============================================================================
# Domain API 路由
# ==============================================================================
# 功能：
#   - 定义领域/科目的所有 CRUD API 端点
#   - 支持按年级、学期筛选
#   - 删除时级联删除关联的章节和知识点
#
# 数据流向：
#   前端请求 → API 路由 → 数据库 → 响应
#
# API 端点：
#   POST   /domains           创建领域/科目
#   GET    /domains           获取领域列表（支持按grade/semester筛选，分页）
#   GET    /domains/{id}      获取领域详情
#   PUT    /domains/{id}      更新领域
#   DELETE /domains/{id}      删除领域（级联删除章节和知识点）
# ==============================================================================

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.sqlite.engine import get_db
from app.infrastructure.domain import Domain
from app.schemas.base import APIResponse, PaginatedData
from app.schemas.domain import (
    DomainCreate,
    DomainUpdate,
    DomainResponse,
)

# 创建路由器
router = APIRouter(prefix="/domains", tags=["Domains"])


# ==============================================================================
# 领域/科目 CRUD 端点
# ==============================================================================

@router.post(
    "",
    response_model=APIResponse[DomainResponse],
    summary="创建领域/科目",
    description="创建新的学习领域或科目",
)
def create_domain(
    body: DomainCreate,
    db: Session = Depends(get_db),
) -> APIResponse[DomainResponse]:
    """
    创建领域/科目

    请求体：
        {
          "name": "数据结构",
          "code": "CS201",
          "description": "计算机科学核心课程",
          "grade": "大二",
          "semester": "上",
          "sort_order": 1,
          "is_active": true
        }
    """
    domain = Domain(
        name=body.name,
        code=body.code,
        description=body.description,
        grade=body.grade,
        semester=body.semester,
        sort_order=body.sort_order,
        is_active=body.is_active,
    )
    db.add(domain)
    db.commit()
    db.refresh(domain)

    return APIResponse(code=200, message="领域创建成功", data=DomainResponse.model_validate(domain))


@router.get(
    "",
    response_model=APIResponse[PaginatedData[DomainResponse]],
    summary="获取领域列表",
    description="分页获取领域列表，支持按年级和学期筛选",
)
def list_domains(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    grade: Optional[str] = Query(None, description="按年级筛选：大一/大二/大三/大四"),
    semester: Optional[str] = Query(None, description="按学期筛选：上/下"),
    db: Session = Depends(get_db),
) -> APIResponse[PaginatedData[DomainResponse]]:
    """获取领域列表"""
    query = db.query(Domain)

    # 筛选条件
    if grade:
        query = query.filter(Domain.grade == grade)
    if semester:
        query = query.filter(Domain.semester == semester)

    # 查询总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    domains = (
        query
        .order_by(Domain.sort_order.asc(), Domain.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return APIResponse(
        code=200,
        message="success",
        data=PaginatedData(
            items=[DomainResponse.model_validate(d) for d in domains],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{domain_id}",
    response_model=APIResponse[DomainResponse],
    summary="获取领域详情",
    description="根据 ID 获取领域详情",
)
def get_domain(
    domain_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[DomainResponse]:
    """获取领域详情"""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="领域不存在")

    return APIResponse(code=200, message="success", data=DomainResponse.model_validate(domain))


@router.put(
    "/{domain_id}",
    response_model=APIResponse[DomainResponse],
    summary="更新领域",
    description="更新领域/科目的信息",
)
def update_domain(
    domain_id: str,
    body: DomainUpdate,
    db: Session = Depends(get_db),
) -> APIResponse[DomainResponse]:
    """更新领域"""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="领域不存在")

    # 仅更新传入的非空字段
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(domain, field, value)

    db.commit()
    db.refresh(domain)

    return APIResponse(code=200, message="领域更新成功", data=DomainResponse.model_validate(domain))


@router.delete(
    "/{domain_id}",
    response_model=APIResponse[bool],
    summary="删除领域",
    description="删除领域及其关联的所有章节和知识点（级联删除）",
)
def delete_domain(
    domain_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除领域（级联删除章节和知识点）"""
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=404, detail="领域不存在")

    # 级联删除（SQLAlchemy relationship 已配置 cascade）
    db.delete(domain)
    db.commit()

    return APIResponse(code=200, message="删除成功", data=True)
