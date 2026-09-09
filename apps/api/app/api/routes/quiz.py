"""模拟练习（Quiz）API 路由。

端点：
    GET    /quiz/papers/{paper_id}                    试卷详情（含题目）
    GET    /quiz/papers/{paper_id}/download?format=md|json  下载渲染文件
    POST   /quiz/papers/{paper_id}/grade              提交作答 → 判分 + 解析（不落库）

试卷的创建不通过 HTTP：由聊天练习模式的 ``generate_quiz_paper`` 工具
（``DeepAgentsPracticeWorkflowRunner``）直接调用 ``QuizPaperService`` 完成。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.domain.quiz_service import QuizPaperService
from app.infrastructure.files.quiz_file_storage import (
    LocalQuizFileStorage,
    get_local_quiz_file_storage,
)
from app.infrastructure.sqlite.engine import get_db
from app.schemas.base import APIResponse
from app.schemas.quiz import QuizGradeRequest, QuizGradeResponse, QuizPaperDetailResponse

router = APIRouter(prefix="/quiz", tags=["Quiz"])

_MEDIA_TYPES = {
    "md": "text/markdown; charset=utf-8",
    "json": "application/json; charset=utf-8",
}


def get_quiz_service(db: Session = Depends(get_db)) -> QuizPaperService:
    """装配试卷服务：注入 DB 会话与本地文件存储。"""
    return QuizPaperService(db, get_local_quiz_file_storage())


def get_quiz_file_storage() -> LocalQuizFileStorage:
    """装配试卷导出文件存储（与试卷服务共享同一 files 根目录）。"""
    return get_local_quiz_file_storage()


@router.get(
    "/papers/{paper_id}",
    response_model=APIResponse[QuizPaperDetailResponse],
    summary="获取试卷详情",
)
def get_paper(
    paper_id: str,
    service: QuizPaperService = Depends(get_quiz_service),
) -> APIResponse[QuizPaperDetailResponse]:
    detail = service.get_paper(paper_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="试卷不存在")
    return APIResponse(data=detail, message="获取成功")


@router.get(
    "/papers/{paper_id}/download",
    response_class=FileResponse,
    summary="下载试卷渲染文件（markdown/json）",
)
def download_paper(
    paper_id: str,
    format: str = Query("md", pattern="^(md|json)$", description="导出格式：md/json"),
    service: QuizPaperService = Depends(get_quiz_service),
    file_storage: LocalQuizFileStorage = Depends(get_quiz_file_storage),
) -> FileResponse:
    relative_path, filename = service.resolve_export_file(paper_id, format)
    if relative_path is None:
        raise HTTPException(status_code=404, detail="试卷不存在或导出文件缺失")
    file_path = file_storage.resolve(relative_path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="导出文件缺失")
    return FileResponse(
        path=file_path,
        media_type=_MEDIA_TYPES[format],
        filename=filename,
        content_disposition_type="attachment",
    )


@router.post(
    "/papers/{paper_id}/grade",
    response_model=APIResponse[QuizGradeResponse],
    summary="提交作答并判分（不落库）",
)
def grade_paper(
    paper_id: str,
    body: QuizGradeRequest,
    service: QuizPaperService = Depends(get_quiz_service),
) -> APIResponse[QuizGradeResponse]:
    detail = service.get_paper(paper_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="试卷不存在")
    return APIResponse(
        data=QuizPaperService.grade_paper(detail, body.answers),
        message="判分完成",
    )
