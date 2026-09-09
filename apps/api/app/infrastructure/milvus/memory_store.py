"""可参数化 schema 的 Milvus Lite collection 工厂。

与 `infrastructure/milvus/milvus_store.py` 的差异：后者为知识切片硬编码了
chunk_id/document_id/... 业务字段；本类通过 `MilvusFieldSpec` 描述任意 schema，
供 L0/L1 各自 collection 复用。lazy-import + _ensure_collection + load_collection
模式照搬既有实现。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from app.core.config import Settings


_GRPC_OPTIONS = {
    "grpc.keepalive_time_ms": 300_000,
    "grpc.keepalive_timeout_ms": 20_000,
    "grpc.keepalive_permit_without_calls": False,
}

logger = logging.getLogger(__name__)


class MilvusFieldType(str, Enum):
    VARCHAR = "VARCHAR"
    INT64 = "INT64"
    BOOL = "BOOL"
    JSON = "JSON"
    FLOAT_VECTOR = "FLOAT_VECTOR"


@dataclass(frozen=True)
class MilvusFieldSpec:
    name: str
    field_type: MilvusFieldType
    is_primary: bool = False
    max_length: int | None = None  # VARCHAR only
    dim: int | None = None         # FLOAT_VECTOR only


@dataclass(frozen=True)
class MilvusMemoryHit:
    id: str
    score: float
    fields: dict[str, Any]


def l0_collection_fields(dimension: int) -> list[MilvusFieldSpec]:
    """Define the L0 message collection schema."""
    return [
        MilvusFieldSpec("id", MilvusFieldType.VARCHAR, is_primary=True, max_length=64),
        MilvusFieldSpec("session_id", MilvusFieldType.VARCHAR, max_length=64),
        MilvusFieldSpec("content", MilvusFieldType.VARCHAR, max_length=65535),
        MilvusFieldSpec("recorded_at_ms", MilvusFieldType.INT64),
        MilvusFieldSpec("vector", MilvusFieldType.FLOAT_VECTOR, dim=dimension),
    ]


class MilvusMemoryVectorStore:
    """可参数化 schema 的向量 collection：建/写/删/带 filter 搜索。

    同步方法：`pymilvus.MilvusClient` 本身同步，原语只封装客户端、不做 IO 调度；
    若调用方（Phase 1/2 service）需要异步，用 `asyncio.to_thread` 在外层包一层，
    不在原语层做假异步（对应 backend.md §3）。
    """

    def __init__(
        self,
        uri: Path,
        collection_name: str,
        fields: list[MilvusFieldSpec],
        metric_type: str = "COSINE",
    ) -> None:
        self._uri = str(uri)
        self._collection_name = collection_name
        self._fields = fields
        self._metric_type = metric_type
        self._client: Any | None = None
        self._vector_field = self._resolve_vector_field()
        self._primary_field = self._resolve_primary_field()

    def _resolve_vector_field(self) -> str:
        vector_fields = [f.name for f in self._fields if f.field_type is MilvusFieldType.FLOAT_VECTOR]
        if not vector_fields:
            raise ValueError("MilvusMemoryVectorStore 至少需要一个 FLOAT_VECTOR 字段")
        return vector_fields[0]

    def _resolve_primary_field(self) -> str:
        primary_fields = [f.name for f in self._fields if f.is_primary]
        if not primary_fields:
            raise ValueError("MilvusMemoryVectorStore 需要一个 is_primary=True 的主键字段")
        return primary_fields[0]

    def _scalar_fields(self) -> list[str]:
        return [f.name for f in self._fields if f.field_type is not MilvusFieldType.FLOAT_VECTOR]

    def _ensure_client(self) -> Any:
        if self._client is None:
            from pymilvus import MilvusClient

            self._client = MilvusClient(uri=self._uri, grpc_options=_GRPC_OPTIONS)
            self._ensure_collection()
        return self._client

    def _ensure_collection(self) -> None:
        if not self._client.has_collection(self._collection_name):
            from pymilvus import DataType

            dtype_map = {
                MilvusFieldType.VARCHAR: DataType.VARCHAR,
                MilvusFieldType.INT64: DataType.INT64,
                MilvusFieldType.BOOL: DataType.BOOL,
                MilvusFieldType.JSON: DataType.JSON,
                MilvusFieldType.FLOAT_VECTOR: DataType.FLOAT_VECTOR,
            }
            schema = self._client.create_schema(auto_id=False, enable_dynamic_field=False)
            for spec in self._fields:
                kwargs: dict[str, Any] = {
                    "field_name": spec.name,
                    "datatype": dtype_map[spec.field_type],
                    "is_primary": spec.is_primary,
                }
                if spec.max_length is not None:
                    kwargs["max_length"] = spec.max_length
                if spec.dim is not None:
                    kwargs["dim"] = spec.dim
                schema.add_field(**kwargs)

            index_params = self._client.prepare_index_params()
            index_params.add_index(
                field_name=self._vector_field,
                index_type="AUTOINDEX",
                metric_type=self._metric_type,
            )
            self._client.create_collection(
                self._collection_name,
                schema=schema,
                index_params=index_params,
            )
        self._client.load_collection(self._collection_name)

    def insert(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        client = self._ensure_client()
        result = client.insert(self._collection_name, data=rows)
        return int(result.get("insert_count", len(rows)))

    def search(
        self,
        query_vector: list[float],
        top_k: int,
        *,
        filter: str | None = None,
        output_fields: list[str] | None = None,
    ) -> list[MilvusMemoryHit]:
        client = self._ensure_client()
        kwargs: dict[str, Any] = {
            "collection_name": self._collection_name,
            "data": [query_vector],
            "limit": top_k,
            "output_fields": output_fields or self._scalar_fields(),
            "search_params": {"metric_type": self._metric_type},
        }
        if filter is not None:
            kwargs["filter"] = filter
        results = client.search(**kwargs)
        hits: list[MilvusMemoryHit] = []
        for row in results[0] if results else []:
            entity = row.get("entity", {})
            hits.append(
                MilvusMemoryHit(
                    id=str(row.get(self._primary_field, "")),
                    score=float(row.get("distance", 0.0)),
                    fields={k: v for k, v in entity.items()},
                )
            )
        return hits

    def delete(self, filter: str) -> None:
        client = self._ensure_client()
        client.delete(self._collection_name, filter=filter)

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:  # pragma: no cover - defensive close
                logger.warning("Milvus memory client close failed: %s", exc)
            self._client = None


def create_memory_vector_store(settings: Settings) -> MilvusMemoryVectorStore:
    """Create an L0 vector store without retaining process-global state."""
    settings.milvus_lite_path.parent.mkdir(parents=True, exist_ok=True)
    return MilvusMemoryVectorStore(
        uri=settings.milvus_lite_path,
        collection_name=settings.memory_milvus_l0_collection_name,
        fields=l0_collection_fields(settings.embedding_dimension),
    )
