"""Async SQLite checkpointer provider for deepagents chat threads.

提供进程级 ``AsyncSqliteSaver`` 单例，用于持久化智能体会话状态
（``thread_id = session_id``）。消息压缩中间件据此按对话记录数触发压缩。
"""

from __future__ import annotations

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from app.core.config import Settings, get_settings

_connection: aiosqlite.Connection | None = None
_checkpointer: AsyncSqliteSaver | None = None


async def get_chat_checkpointer(settings: Settings | None = None) -> AsyncSqliteSaver:
    """Return a process-level async SQLite checkpointer for chat threads."""
    global _connection, _checkpointer

    if _checkpointer is not None:
        return _checkpointer

    settings = settings or get_settings()
    settings.langgraph_checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    _connection = await aiosqlite.connect(str(settings.langgraph_checkpoint_path))
    _checkpointer = AsyncSqliteSaver(_connection)
    await _checkpointer.setup()
    return _checkpointer


async def close_chat_checkpointer() -> None:
    """Close the process-level checkpointer connection."""
    global _connection, _checkpointer
    if _connection is not None:
        await _connection.close()
    _connection = None
    _checkpointer = None
