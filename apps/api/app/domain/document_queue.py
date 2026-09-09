"""基于进程内队列的异步文档处理服务。

上传接口把文档入队后立即返回，后台 worker 从队列取记录并执行处理管线，
文档状态（pending → processing → completed/failed）持久化到 documents 表，
供文件列表与进度页查询。

设计说明：
- 继承 ``DocumentProcessingService`` 复用其索引与错误处理逻辑
  （``_index_chunks`` / ``_readable_error``），不改动核心业务类内部逻辑，
  符合架构铁律（优先新建子类/接口实现）。
- 默认单 worker 顺序处理：SQLAlchemy 会话在多个协程间并发读写不安全，
  且处理管线依赖 LLM 异步等待，单 worker 已能满足"上传不阻塞、多文件排队
  后台处理"的要求。如需并发需为每个 job 建立独立会话（超出当前范围）。
"""

from __future__ import annotations

import asyncio
import logging

from app.domain.document_service import DocumentProcessingService
from app.domain.ports.documents import DocumentRepository
from app.domain.ports.embeddings import EmbeddingProvider
from app.domain.ports.file_storage import DocumentFileStorage
from app.domain.ports.knowledge_pipeline import KnowledgePipeline
from app.domain.ports.semantic_store import SemanticVectorStore
from app.schemas.documents import DocumentRecordResponse

logger = logging.getLogger(__name__)


class DocumentProcessingQueue(DocumentProcessingService):
    """进程内队列：上传即入队，后台 worker 顺序处理文档。"""

    def __init__(
        self,
        repository: DocumentRepository,
        pipeline: KnowledgePipeline,
        embedding_provider: EmbeddingProvider,
        vector_store: SemanticVectorStore,
        file_storage: DocumentFileStorage,
        max_workers: int = 1,
    ) -> None:
        super().__init__(
            repository=repository,
            pipeline=pipeline,
            embedding_provider=embedding_provider,
            vector_store=vector_store,
            file_storage=file_storage,
        )
        self.max_workers = max(1, max_workers)
        self._queue: asyncio.Queue[str] = asyncio.Queue()
        self._workers: list[asyncio.Task] = []

    def start(self) -> None:
        """启动后台 worker；幂等，重复调用不重复创建。

        启动前先恢复上次未完成（pending / processing）的记录，
        避免重启或 worker 被取消后文档卡在 processing 状态。
        """
        if self._workers:
            return
        for record in self.repository.list_unfinished():
            self._queue.put_nowait(record.id)
            logger.info("Recovered unfinished document: %s (%s)", record.filename, record.id)
        for index in range(self.max_workers):
            self._workers.append(
                asyncio.create_task(self._worker_loop(), name=f"document-queue-worker-{index}")
            )
        logger.info("Document queue started with %d worker(s)", self.max_workers)

    async def stop(self) -> None:
        """取消并等待所有 worker 退出。"""
        for task in self._workers:
            task.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Document queue stopped")

    def enqueue(self, filename: str, content_type: str, file_bytes: bytes, course_name: str = "未分类", academic_year: int = 0, semester: int = 1) -> DocumentRecordResponse:
        """创建 pending 记录、保存原始文件并放入队列，立即返回。"""
        record = self.repository.create_pending(filename, content_type, len(file_bytes), course_name, academic_year, semester)
        stored_path = self.file_storage.save(record.id, filename, file_bytes)
        self.repository.set_file_path(record.id, stored_path)
        self._queue.put_nowait(record.id)
        logger.info("Document queued: %s (%s)", filename, record.id)
        # create_pending 返回的记录不含 file_path，重新读取以获得完整记录
        return self.repository.get_record(record.id) or record

    async def _worker_loop(self) -> None:
        while True:
            record_id = await self._queue.get()
            try:
                await self._process(record_id)
            except Exception as exc:
                logger.exception("Queue worker failed for document %s: %s", record_id, exc)
                try:
                    self.repository.mark_failed(record_id, f"队列处理异常: {type(exc).__name__}")
                except Exception:
                    pass
            finally:
                self._queue.task_done()

    async def _process(self, record_id: str) -> None:
        """对一条已入队记录执行处理管线并落库。"""
        if (
            self.pipeline is None
            or self.embedding_provider is None
            or self.vector_store is None
        ):
            self.repository.mark_failed(record_id, "文档处理依赖未配置")
            return

        record = self.repository.get_record(record_id)
        if record is None:
            return
        self.repository.mark_processing(record_id)

        if not record.file_path:
            self.repository.mark_failed(record_id, "原始文件路径缺失")
            return
        file_path = self.file_storage.resolve(record.file_path)
        if file_path is None:
            self.repository.mark_failed(record_id, "原始文件缺失")
            return

        file_bytes = await asyncio.to_thread(file_path.read_bytes)
        try:
            result = await self.pipeline.run(
                document_id=record.id,
                filename=record.filename,
                file_bytes=file_bytes,
            )
            chunks = self.repository.persist_chunks(record.id, result.knowledge_points)
            indexed_count = await self._index_chunks(record, chunks)
            if indexed_count != len(chunks):
                raise RuntimeError(
                    f"向量索引数量不一致：expected={len(chunks)}, actual={indexed_count}"
                )
            logger.info("Document processed via queue: %s (%d chunks)", record.filename, len(chunks))
            self.repository.mark_completed(record.id, len(result.chapters), len(chunks))
        except Exception as exc:
            self.repository.rollback()
            try:
                await self.vector_store.delete_by_document(record_id)
            except Exception as cleanup_exc:
                logger.error(
                    "Vector cleanup failed after queue processing error: %s: %s",
                    type(cleanup_exc).__name__,
                    cleanup_exc,
                )
            logger.exception("Document queue processing failed: %s", record.filename)
            self.repository.mark_failed(record_id, self._readable_error(exc))
