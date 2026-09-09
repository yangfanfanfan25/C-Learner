# ==============================================================================
# ExamRecord API 路由（出题记录）
# ==============================================================================
# 功能：
#   - 定义出题记录的所有 API 端点
#   - 记录 LLM 基于知识点组合生成的题目
#   - 支持按 domain/difficulty 筛选
#
# 数据流向：
#   前端请求 → API 路由 → 数据库 → 响应
#
# API 端点：
#   POST   /exam-records              创建出题记录
#   GET    /exam-records              获取出题记录列表（支持按domain/difficulty筛选，分页）
#   GET    /exam-records/{id}         获取出题记录详情
#   PUT    /exam-records/{id}/use     标记为已使用
#   DELETE /exam-records/{id}         删除出题记录
# ==============================================================================

import json
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.infrastructure.sqlite.engine import get_db
from app.infrastructure.exam import ExamRecord
from app.schemas.base import APIResponse, PaginatedData
from app.schemas.exam_record import (
    ExamRecordCreate,
    ExamRecordResponse,
)

# 创建路由器
router = APIRouter(prefix="/exam-records", tags=["Exam Records"])


# ==============================================================================
# 辅助函数
# ==============================================================================

def _build_exam_record_response(record: ExamRecord) -> ExamRecordResponse:
    """构建出题记录响应（处理 JSON 字段反序列化）"""
    return ExamRecordResponse(
        id=record.id,
        knowledge_combo=json.loads(record.knowledge_combo) if isinstance(record.knowledge_combo, str) else record.knowledge_combo,
        difficulty=record.difficulty,
        question_type=record.question_type,
        question_text=record.question_text,
        answer_text=record.answer_text,
        domain=record.domain,
        is_used=record.is_used,
        created_at=record.created_at,
    )


# ==============================================================================
# 出题记录端点
# ==============================================================================

@router.post(
    "",
    response_model=APIResponse[ExamRecordResponse],
    summary="创建出题记录",
    description="创建基于知识点组合的出题记录",
)
def create_exam_record(
    body: ExamRecordCreate,
    db: Session = Depends(get_db),
) -> APIResponse[ExamRecordResponse]:
    """
    创建出题记录

    请求体：
        {
          "knowledge_combo": ["id1", "id2"],
          "difficulty": 2,
          "question_type": "choice",
          "domain": "数据结构"
        }
    """
    record = ExamRecord(
        knowledge_combo=json.dumps(body.knowledge_combo, ensure_ascii=False),
        difficulty=body.difficulty,
        question_type=body.question_type,
        domain=body.domain,
        is_used=False,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return APIResponse(
        code=200,
        message="出题记录创建成功",
        data=_build_exam_record_response(record),
    )


@router.get(
    "",
    response_model=APIResponse[PaginatedData[ExamRecordResponse]],
    summary="获取出题记录列表",
    description="分页获取出题记录，支持按 domain 和 difficulty 筛选",
)
def list_exam_records(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    domain: Optional[str] = Query(None, description="按领域筛选"),
    difficulty: Optional[int] = Query(None, description="按难度筛选：1=基础, 2=进阶, 3=综合"),
    db: Session = Depends(get_db),
) -> APIResponse[PaginatedData[ExamRecordResponse]]:
    """获取出题记录列表"""
    query = db.query(ExamRecord)

    # 筛选条件
    if domain:
        query = query.filter(ExamRecord.domain == domain)
    if difficulty is not None:
        query = query.filter(ExamRecord.difficulty == difficulty)

    # 查询总数
    total = query.count()

    # 分页查询
    offset = (page - 1) * page_size
    records = (
        query
        .order_by(ExamRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    total_pages = math.ceil(total / page_size) if total > 0 else 0

    return APIResponse(
        code=200,
        message="success",
        data=PaginatedData(
            items=[_build_exam_record_response(r) for r in records],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get(
    "/{record_id}",
    response_model=APIResponse[ExamRecordResponse],
    summary="获取出题记录详情",
    description="根据 ID 获取出题记录详情",
)
def get_exam_record(
    record_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ExamRecordResponse]:
    """获取出题记录详情"""
    record = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="出题记录不存在")

    return APIResponse(
        code=200,
        message="success",
        data=_build_exam_record_response(record),
    )


@router.put(
    "/{record_id}/use",
    response_model=APIResponse[ExamRecordResponse],
    summary="标记为已使用",
    description="将出题记录标记为已使用状态",
)
def mark_as_used(
    record_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[ExamRecordResponse]:
    """标记出题记录为已使用"""
    record = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="出题记录不存在")

    record.is_used = True
    db.commit()
    db.refresh(record)

    return APIResponse(
        code=200,
        message="已标记为使用",
        data=_build_exam_record_response(record),
    )


@router.delete(
    "/{record_id}",
    response_model=APIResponse[bool],
    summary="删除出题记录",
    description="删除指定的出题记录",
)
def delete_exam_record(
    record_id: str,
    db: Session = Depends(get_db),
) -> APIResponse[bool]:
    """删除出题记录"""
    record = db.query(ExamRecord).filter(ExamRecord.id == record_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="出题记录不存在")

    db.delete(record)
    db.commit()

    return APIResponse(code=200, message="删除成功", data=True)
