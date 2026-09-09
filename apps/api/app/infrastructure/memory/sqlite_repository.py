"""L0/L1 结构化真源 + FTS5 关键词 + 游标的 SQLite 仓库。"""

from __future__ import annotations

from contextlib import closing

from sqlalchemy import func

from app.domain.ports.database import DatabaseSession
from app.infrastructure.memory.fts import FtsHit, create_fts5_table, fts_search
from app.infrastructure.memory.models import MemoryCursor, MemoryL0Message, MemoryL1Atom
from app.infrastructure.sqlite.provider import SQLiteProvider
from app.schemas.memory import L0Message, MemoryAtom, MemoryType

L0_FTS_TABLE = "l0_conversation_fts"
L1_FTS_TABLE = "l1_memory_fts"


def init_fts(sqlite_provider: SQLiteProvider) -> None:
    """建 L0/L1 FTS5 虚拟表（raw DDL，不进 Alembic；幂等）。"""
    with closing(sqlite_provider.open_connection()) as conn:
        create_fts5_table(conn, L0_FTS_TABLE, ["message_id", "content"], tokenize="trigram")
        create_fts5_table(conn, L1_FTS_TABLE, ["memory_id", "content"], tokenize="trigram")
        conn.commit()


class SqliteMemoryRepository:
    """L0 消息 + L1 原子 + 游标的 SQLite 实现（SQLAlchemy ORM + raw FTS5）。"""

    def __init__(self, db: DatabaseSession, sqlite_provider: SQLiteProvider) -> None:
        self._db = db
        self._sqlite = sqlite_provider

    def append(self, msg: L0Message) -> None:
        """落库 ORM 行 + FTS5 索引（两段写、非原子；FTS5 失败会抛出）。"""
        values = msg.model_dump()
        values["context"] = msg.context.model_dump(mode="json")
        self._db.add(MemoryL0Message(**values))
        self._db.commit()
        with closing(self._sqlite.open_connection()) as conn:
            conn.execute(
                f"INSERT INTO {L0_FTS_TABLE} (message_id, content) VALUES (?, ?)",
                (msg.id, msg.content),
            )
            conn.commit()

    def list_since(self, cursor_ms: int, limit: int) -> list[L0Message]:
        """按 recorded_at_ms 游标增量取（升序、限 limit）。"""
        rows = (
            self._db.query(MemoryL0Message)
            .filter(MemoryL0Message.recorded_at_ms > cursor_ms)
            .order_by(MemoryL0Message.recorded_at_ms.asc())
            .limit(limit)
            .all()
        )
        return [
            L0Message.model_validate({**row.__dict__, "context": row.context})
            for row in rows
        ]

    def count_since(self, cursor_ms: int) -> int:
        return (
            self._db.query(func.count(MemoryL0Message.id))
            .filter(MemoryL0Message.recorded_at_ms > cursor_ms)
            .scalar()
            or 0
        )

    def search_fts(self, query: str, top_k: int) -> list[FtsHit]:
        with closing(self._sqlite.open_connection()) as conn:
            return fts_search(conn, L0_FTS_TABLE, query, top_k)

    def get_cursor(self, key: str) -> int | None:
        row = self._db.query(MemoryCursor).filter(MemoryCursor.key == key).first()
        return int(row.value) if row is not None else None

    def set_cursor(self, key: str, value: int) -> None:
        row = self._db.query(MemoryCursor).filter(MemoryCursor.key == key).first()
        if row is None:
            self._db.add(MemoryCursor(key=key, value=str(value)))
        else:
            row.value = str(value)
        self._db.commit()

    # -- L1 atom -----------------------------------------------------------

    def append_atom(self, atom: MemoryAtom) -> None:
        """落库 ORM 行 + FTS5 索引（非原子两段写）。"""
        self._db.add(
            MemoryL1Atom(
                id=atom.id,
                session_id=atom.session_id,
                content=atom.content,
                type=atom.type.value,
                priority=atom.priority,
                source_message_ids=atom.source_message_ids or None,
                scene_name=atom.scene_name,
                activity=atom.activity.value,
                subject=atom.subject,
                scope=atom.scope,
                metadata_=atom.metadata or None,
                timestamps=atom.timestamps or None,
                version=atom.version,
                created_at_ms=atom.created_at_ms,
                updated_at_ms=atom.updated_at_ms,
            )
        )
        self._db.commit()
        with closing(self._sqlite.open_connection()) as conn:
            conn.execute(
                f"INSERT INTO {L1_FTS_TABLE} (memory_id, content) VALUES (?, ?)",
                (atom.id, atom.content),
            )
            conn.commit()

    def list_atoms_since(self, updated_after_ms: int, limit: int) -> list[MemoryAtom]:
        rows = (
            self._db.query(MemoryL1Atom)
            .filter(MemoryL1Atom.updated_at_ms > updated_after_ms)
            .order_by(MemoryL1Atom.updated_at_ms.asc())
            .limit(limit)
            .all()
        )
        return [self._to_atom(row) for row in rows]

    def get_atoms_by_ids(self, ids: list[str]) -> list[MemoryAtom]:
        """按 id 批量取完整记忆原子（保持入参顺序）。"""
        if not ids:
            return []
        rows = self._db.query(MemoryL1Atom).filter(MemoryL1Atom.id.in_(ids)).all()
        by_id = {row.id: row for row in rows}
        return [self._to_atom(by_id[i]) for i in ids if i in by_id]

    def delete_atoms(self, ids: list[str]) -> None:
        """SQLite 行删 + FTS5 同步删（保证关键词召回不再吐旧行）。"""
        if not ids:
            return
        rows = self._db.query(MemoryL1Atom).filter(MemoryL1Atom.id.in_(ids)).all()
        for row in rows:
            self._db.delete(row)
        self._db.commit()
        with closing(self._sqlite.open_connection()) as conn:
            for atom_id in ids:
                # FTS5 虚拟表直接支持 DELETE FROM（实测 SQLite 3.53.1），
                # 无需 FTS3/FTS4 那套 INSERT ... VALUES('delete', ...) 特殊命令。
                conn.execute(
                    f"DELETE FROM {L1_FTS_TABLE} WHERE memory_id = ?",
                    (atom_id,),
                )
            conn.commit()

    def search_atoms_fts(self, query: str, top_k: int) -> list[FtsHit]:
        with closing(self._sqlite.open_connection()) as conn:
            return fts_search(conn, L1_FTS_TABLE, query, top_k)

    @staticmethod
    def _to_atom(row: MemoryL1Atom) -> MemoryAtom:
        return MemoryAtom(
            id=row.id,
            session_id=row.session_id,
            content=row.content,
            type=MemoryType(row.type),
            priority=row.priority,
            source_message_ids=list(row.source_message_ids or []),
            scene_name=row.scene_name,
            activity=row.activity,
            subject=row.subject,
            scope=row.scope,
            metadata=dict(row.metadata_ or {}),
            timestamps=list(row.timestamps or []),
            version=row.version,
            created_at_ms=row.created_at_ms,
            updated_at_ms=row.updated_at_ms,
        )
