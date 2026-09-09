"""文档上传、处理与持久化路由。"""

from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.domain.document_queue import DocumentProcessingQueue
from app.domain.document_service import DocumentProcessingService
from app.domain.knowledge_markdown import build_knowledge_markdown
from app.infrastructure.documents import SQLAlchemyDocumentRepository
from app.infrastructure.embeddings import get_embedding_provider
from app.infrastructure.files import LocalFileStorage, get_local_file_storage
from app.infrastructure.knowledge.pipeline import SimpleKnowledgePipeline
from app.infrastructure.llm.provider import create_chat_model
from app.infrastructure.milvus import get_milvus_vector_store
from app.infrastructure.sqlite.engine import get_db, get_session_factory
from app.schemas.base import APIResponse, PaginatedData
from app.schemas.documents import (
    DocumentDetailResponse,
    DocumentProcessResponse,
    DocumentRecordResponse,
)

router = APIRouter(prefix="/documents", tags=["documents"])

# 支持的文件扩展名（当前不处理图片文件）
_SUPPORTED_EXTENSIONS = {
    ".pdf", ".pptx", ".docx", ".doc", ".xlsx", ".xls", ".csv",
    ".txt", ".text", ".md", ".markdown", ".json", ".jsonl",
    ".html", ".htm", ".epub", ".ipynb", ".msg", ".zip",
}
_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff"}
_MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB


def create_document_queue(settings: Settings | None = None) -> DocumentProcessingQueue:
    """组合根：创建全局文档处理队列（懒初始化，首个上传请求时构建并启动 worker）。

    队列持有独立的长生命周期 SQLAlchemy 会话，不随请求关闭。
    """
    if settings is None:
        settings = get_settings()
    session = get_session_factory()()
    return DocumentProcessingQueue(
        repository=SQLAlchemyDocumentRepository(session),
        pipeline=SimpleKnowledgePipeline(
            model=create_chat_model(settings),
            settings=settings,
        ),
        embedding_provider=get_embedding_provider(settings),
        vector_store=get_milvus_vector_store(settings),
        file_storage=get_local_file_storage(settings),
        max_workers=settings.document_queue_max_workers,
    )


async def get_document_queue(request: Request) -> DocumentProcessingQueue:
    """获取全局文档处理队列；首次调用时懒初始化并启动后台 worker。

    声明为 async 依赖以避免 FastAPI 将同步依赖放入线程池造成并发重复初始化。
    """
    queue = getattr(request.app.state, "document_queue", None)
    if queue is None:
        queue = create_document_queue()
        queue.start()
        request.app.state.document_queue = queue
    return queue


def get_document_query_service(
    db: Session = Depends(get_db),
) -> DocumentProcessingService:
    """查询文档只依赖 SQLite，不初始化 LLM、Embedding 或 Milvus。"""
    return DocumentProcessingService(repository=SQLAlchemyDocumentRepository(db))


def get_document_delete_service(
    db: Session = Depends(get_db),
) -> DocumentProcessingService:
    """删除文档装配 SQLite、Milvus 与文件存储。"""
    return DocumentProcessingService(
        repository=SQLAlchemyDocumentRepository(db),
        vector_store=get_milvus_vector_store(),
        file_storage=get_local_file_storage(),
    )


def get_document_file_service(
    db: Session = Depends(get_db),
) -> tuple[SQLAlchemyDocumentRepository, LocalFileStorage]:
    """下载原始文件只读依赖：仅装配 SQLite 与文件存储，不初始化 LLM/Embedding/Milvus。"""
    return SQLAlchemyDocumentRepository(db), get_local_file_storage()


def _validate_upload(filename: str, content: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix in _IMAGE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持图片文件（{suffix or filename}）",
        )
    if suffix not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的文件类型: {suffix or filename}",
        )
    if len(content) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail="文件大小超过限制，最大允许 100MB",
        )
    return suffix


def _attachment_response(content: bytes, media_type: str, filename: str) -> Response:
    """构造附件下载响应，中文文件名使用 RFC 5987 编码，并保留 ASCII 回退。"""
    ascii_fallback = filename.encode("ascii", "ignore").decode() or "download"
    disposition = (
        f"attachment; filename=\"{ascii_fallback}\"; "
        f"filename*=UTF-8''{quote(filename)}"
    )
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": disposition},
    )


def _build_knowledge_markdown(detail: DocumentDetailResponse) -> str:
    """把知识切片按章节分组导出为 Markdown 文本（委托共享纯函数，输出不变）。"""
    return build_knowledge_markdown(detail)


@router.post(
    "/process",
    response_model=APIResponse[DocumentProcessResponse],
    summary="上传文档并入队异步处理",
)
async def process_document(
    file: UploadFile = File(...),
    course_name: str = Form(..., min_length=1, max_length=200),
    academic_year: int = Form(..., ge=1, le=9999),
    semester: int = Form(..., ge=1, le=2),
    queue: DocumentProcessingQueue = Depends(get_document_queue),
) -> APIResponse[DocumentProcessResponse]:
    """读取文件 → 校验 → 入队后立即返回；后台 worker 异步执行处理管线。"""
    content = await file.read()
    filename = file.filename or "uploaded"
    _validate_upload(filename, content)
    course_name = course_name.strip()
    if not course_name:
        raise HTTPException(status_code=422, detail="课程名称不能为空")

    record = queue.enqueue(
        filename=filename,
        content_type=file.content_type or "application/octet-stream",
        file_bytes=content,
        course_name=course_name,
        academic_year=academic_year,
        semester=semester,
    )
    return APIResponse(
        data=DocumentProcessResponse(
            document=record,
            chapter_count=0,
            chunk_count=0,
            indexed_count=0,
        ),
        message="已加入处理队列",
    )


@router.get(
    "",
    response_model=APIResponse[PaginatedData[DocumentRecordResponse]],
    summary="分页列出已处理文档",
)
def list_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    service: DocumentProcessingService = Depends(get_document_query_service),
) -> APIResponse[PaginatedData[DocumentRecordResponse]]:
    return APIResponse(data=service.list_documents(page, page_size))


@router.get(
    "/{document_id}/file",
    response_class=FileResponse,
    summary="下载文档原始文件",
)
def download_document_file(
    document_id: str,
    file_service: tuple[SQLAlchemyDocumentRepository, LocalFileStorage] = Depends(
        get_document_file_service,
    ),
) -> FileResponse:
    """以附件方式下载原始文件；记录不存在、未保存文件或磁盘缺失时返回 404。"""
    repository, file_storage = file_service
    record = repository.get_document(document_id)
    if record is None or not record.file_path:
        raise HTTPException(status_code=404, detail="文件不存在")
    file_path = file_storage.resolve(record.file_path)
    if file_path is None:
        raise HTTPException(status_code=404, detail="文件不存在")
    return FileResponse(
        path=file_path,
        media_type=record.content_type or "application/octet-stream",
        filename=record.filename,
        content_disposition_type="attachment",
    )


@router.get(
    "/{document_id}/knowledge.md",
    response_class=Response,
    summary="下载加工后的知识点（Markdown）",
)
def download_knowledge_markdown(
    document_id: str,
    service: DocumentProcessingService = Depends(get_document_query_service),
) -> Response:
    """把已提取的知识切片导出为 Markdown 附件；文档不存在或无切片时返回 404。"""
    detail = service.get_document(document_id)
    if detail is None or not detail.chunks:
        raise HTTPException(status_code=404, detail="该文档暂无知识切片")
    markdown = _build_knowledge_markdown(detail)
    stem = Path(detail.filename).stem or "knowledge"
    return _attachment_response(
        content=markdown.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        filename=f"{stem}.md",
    )


@router.get(
    "/{document_id}",
    response_model=APIResponse[DocumentDetailResponse],
    summary="获取文档详情（含知识切片摘要）",
)
def get_document(
    document_id: str,
    service: DocumentProcessingService = Depends(get_document_query_service),
) -> APIResponse[DocumentDetailResponse]:
    detail = service.get_document(document_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return APIResponse(data=detail)


@router.delete(
    "/{document_id}",
    response_model=APIResponse[bool],
    summary="删除文档（SQLite 记录与 Milvus 向量）",
)
async def delete_document(
    document_id: str,
    service: DocumentProcessingService = Depends(get_document_delete_service),
) -> APIResponse[bool]:
    try:
        deleted = await service.delete_document(document_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="删除文档向量失败") from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="文档不存在")
    return APIResponse(data=True, message="删除成功")
