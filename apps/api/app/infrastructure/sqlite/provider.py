"""SQLite connection provider.

Wires the local SQLite database path and exposes thin helpers for opening
connections and bootstrapping the minimum schema.  All public behaviour is
explicit — no background connections, no hidden side-effects.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.core.config import Settings, get_settings

_FOREIGN_KEYS_PRAGMA = "PRAGMA foreign_keys = ON"

_MINIMUM_SCHEMA = """\
CREATE TABLE IF NOT EXISTS app_metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


@dataclass
class SQLiteProvider:
    """Thin wrapper around a local SQLite database file.

    The provider owns the database path and ensures the parent directory
    exists.  Connections are opened on demand — callers are responsible for
    closing them (or using ``connection()`` as a context manager).
    """

    db_path: Path

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    # -- connection helpers ---------------------------------------------------

    def open_connection(self) -> sqlite3.Connection:
        """Return a new connection with foreign-keys enabled."""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute(_FOREIGN_KEYS_PRAGMA)
        conn.row_factory = sqlite3.Row
        return conn

    # -- schema bootstrap -----------------------------------------------------

    def initialize(self) -> None:
        """Create the minimum schema required by the local backend."""
        with self.open_connection() as conn:
            conn.executescript(_MINIMUM_SCHEMA)


def create_sqlite_provider(settings: Settings | None = None) -> SQLiteProvider:
    """Factory that wires the provider to application settings."""
    if settings is None:
        settings = get_settings()
    return SQLiteProvider(db_path=settings.sqlite_path)
