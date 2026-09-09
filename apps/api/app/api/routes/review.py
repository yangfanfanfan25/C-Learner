# ==============================================================================
# Review API 路由（复习记录）
# ==============================================================================
# 功能：
#   - 定义复习记录的所有 API 端点
#   - 基于间隔重复算法（Spaced Repetition）管理复习计划
#   - 支持按 mastery_level 和待复习筛选
#
# 数据流向：
#   前端请求 → API 路由 → 数据库 → 响应
#
# API 端点：
#   POST   /review/records            创建复习记录
#   GET    /review/records            获取复习记录列表（支持按mastery_level/待复习筛选，分页）
#   GET    /review/records/{id}       获取复习记录详情
#   GET    /review/records/catalog/{catalog_id}  按知识点ID获取复习记录
#   PUT    /review/records/{id}       更新复习记录（掌握程度、笔记等）
#   POST   /review/records/{id}/review  执行复习（更新review_count、last_reviewed_at、计算next_review_at）
#   DELETE /review/records/{id}       删除复习记录
#
# 间隔重复算法：
#   next_review_at = now + interval_days
#   interval_days 基于 review_count：
#     review_count 1: 1天
#     review_count 2: 2天
#     review_count 3: 4天
#     review_count 4: 7天
#     review_count 5: 15天
#     review_count >= 6: 30天
#   如果答错（incorrect_count 增加），重置为 1 天
# ==============================================================================

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.sqlite.engine import get_db
from app.infrastructure.review_record import ReviewRecord
from app.schemas.base import APIResponse, PaginatedData
from app.schemas.review import (
    ReviewRecordCreate,
    ReviewRecordUpdate,
    ReviewRecordResponse,
)

# 创建路由器
router = APIRouter(prefix="/review", tags=["Review"])


# ==============================================================================
# 辅助函数
# ==============================================================================

# 间隔重复天数映射
INTERVAL_DAYS_MAP = {
    1: 1,
    2: 2,
    3: 4,
    4: 7,
    5: 15,
}


def _calculate_next_review_at(review_count: int, incorrect_count_increased: bool) -> datetime:
    """
    计算下次复习时间

    间隔重复算法：
        - 根据 review_count 确定间隔天数
        - 如果本次答错（incorrect_count 增加），重置为 1 天
        - review_count >= 6 时固定为 30 天
    """
    now = datetime.now(timezone.utc)

    # 如果答错，重置为 1 天间隔
    if incorrect_count_increased:
        return now + timedelta(days=1)

    # 根据 review_count 获取间隔天数
    interval_days = INTERVAL_DAYS_MAP.get(review_count, 30)

    return now + timedelta(days=interval_days)


def _build_review_response(record: ReviewRecord) -> ReviewRecordResponse:
    """构建复习记录响应"""
    return ReviewRecordResponse(
        id=record.id,
        catalog_id=record.catalog_id,
        review_count=record.review_count,
        last_reviewed_at=record.last_reviewed_at,
        next_review_at=record.next_review_at,
        mastery_level=record.mastery_level,
        incorrect_count=record.incorrect_count,
        notes=record.notes,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


# ==============================================================================
# 复习记录端点
# ==============================================================================

@router.post(
    "/records",
    response_model=APIResponse[ReviewRecordResponse],
    summary="创建复习记录",
    description="为指定知识点创建复习追踪记录",
)
def create_review_record(
    body: ReviewRecordCreate,
    db: Session = Depends(get_db),
) -> APIResponse[ReviewRecordResponse]:
    """
    创建复习记录

    请求体：
        {
          "catalog_id": "550e8400-...",
          "notes": "需要重点复习二分查找的边界条件"
        }
    """
    record = ReviewRecord(
        catalog_id=body.catalog_id,
        notes=body.notes,
        review_count=0,
        mastery_level=0,
        incorrect_count=0,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return APIResponse(
        code=200,
        message="复习记录创建成功",
        data=_build_review_response(record),
    )


@router.get(
    "/records",
    response_model=APIResponse[PaginatedData[ReviewRecordResponse]],
    summary="获取复习记录列表",
    description="分页获取复习记录，支持按 mastery_level 和待复习筛选",
)
def list_review_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    mastery_level: Optional[int] = Query(None, description="按掌握程度筛选：0-5"),
    pending_review: Optional[bool] = Query(None, description="仅显示待复习（next_review_at <= 当前时间）"),
    db: Session = Depends(get_db),
) -> APIResponse[PaginatedData[ReviewRecordResponse]]:
    """获取复习记录列表"""
    query = db.query(ReviewRecord)

    # 筛选条件
    if mastery_level is not None:
        query = query.filter(ReviewRecord.mastery_level == mastery_level)
    if pending_review:
        now = datetime.now(timezone.utc)
        query = query.filter(
            ReviewRecord.next_review_at.isnot(None),
            ReviewRecord.next_review_at <= now,
        )

    # 查询总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    records = (
        query
        .order_by(ReviewRecord.next_review_at.asc().nullslast(), ReviewRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return APIResponse(
        code=200,
        message="success",
        data=PaginatedData(
            items=[_build_review_response(r) for r in records],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/records/{record_id}",
    response_model=APIResponse[ReviewRecordResponse],
    summary="获取复习记录详情",
    description="根据 ID 获取复习记录详情",
)
def get_review_record(
    record_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ReviewRecordResponse]:
    """获取复习记录详情"""
    record = db.query(ReviewRecord).filter(ReviewRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="复习记录不存在")

    return APIResponse(
        code=200,
        message="success",
        data=_build_review_response(record),
    )


@router.get(
    "/records/catalog/{catalog_id}",
    response_model=APIResponse[ReviewRecordResponse],
    summary="按知识点获取复习记录",
    description="根据知识点 ID 获取对应的复习记录",
)
def get_review_by_catalog(
    catalog_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ReviewRecordResponse]:
    """按知识点 ID 获取复习记录"""
    record = db.query(ReviewRecord).filter(ReviewRecord.catalog_id == catalog_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="该知识点的复习记录不存在")

    return APIResponse(
        code=200,
        message="success",
        data=_build_review_response(record),
    )


@router.put(
    "/records/{record_id}",
    response_model=APIResponse[ReviewRecordResponse],
    summary="更新复习记录",
    description="更新复习记录的掌握程度、笔记等信息",
)
def update_review_record(
    record_id: str,
    body: ReviewRecordUpdate,
    db: Session = Depends(get_db),
) -> APIResponse[ReviewRecordResponse]:
    """更新复习记录"""
    record = db.query(ReviewRecord).filter(ReviewRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="复习记录不存在")

    # 仅更新传入的非空字段
    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(record, field, value)

    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)

    return APIResponse(
        code=200,
        message="复习记录更新成功",
        data=_build_review_response(record),
    )


@router.post(
    "/records/{record_id}/review",
    response_model=APIResponse[ReviewRecordResponse],
    summary="执行复习",
    description="执行一次复习操作，更新 review_count、last_reviewed_at，并根据间隔重复算法计算 next_review_at",
)
def execute_review(
    record_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ReviewRecordResponse]:
    """
    执行复习

    说明：
        - 每次调用此接口表示完成一次复习
        - 自动递增 review_count
        - 更新 last_reviewed_at 为当前时间
        - 根据间隔重复算法计算 next_review_at
        - 如果 incorrect_count 在本次增加，则重置间隔为 1 天

    间隔重复算法：
        review_count 1: 1天后复习
        review_count 2: 2天后复习
        review_count 3: 4天后复习
        review_count 4: 7天后复习
        review_count 5: 15天后复习
        review_count >= 6: 30天后复习
    """
    record = db.query(ReviewRecord).filter(ReviewRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="复习记录不存在")

    # 记录复习前的 incorrect_count，用于判断是否答错
    prev_incorrect_count = record.incorrect_count

    # 递增复习次数
    record.review_count += 1
    record.last_reviewed_at = datetime.now(timezone.utc)

    # 判断是否答错（incorrect_count 是否在本次增加）
    # 注意：incorrect_count 的更新由 PUT /records/{id} 接口在复习过程中完成
    # 此处通过比较当前值与 review 开始时的值来判断
    incorrect_count_increased = record.incorrect_count > prev_incorrect_count

    # 计算下次复习时间
    record.next_review_at = _calculate_next_review_at(
        record.review_count,
        incorrect_count_increased,
    )

    record.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(record)

    return APIResponse(
        code=200,
        message="复习完成",
        data=_build_review_response(record),
    )


@router.delete(
    "/records/{record_id}",
    response_model=APIResponse[bool],
    summary="删除复习记录",
    description="删除指定的复习记录",
)
def delete_review_record(
    record_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除复习记录"""
    record = db.query(ReviewRecord).filter(ReviewRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="复习记录不存在")

    db.delete(record)
    db.commit()

    return APIResponse(code=200, message="删除成功", data=True)
