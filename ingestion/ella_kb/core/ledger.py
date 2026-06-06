"""SQLite ledger: the source of truth. Qdrant is a rebuildable derived index — the
ledger records what *should* exist, enabling dedup, crash-resume, no-orphan updates,
and re-embedding on model migration. One row per source (document)."""
from __future__ import annotations

import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path

_SOURCES_DDL = """
CREATE TABLE IF NOT EXISTS sources (
    source_id     TEXT NOT NULL,
    capability    TEXT NOT NULL,
    uri           TEXT,
    title         TEXT,
    content_hash  TEXT NOT NULL,
    user_id       TEXT NOT NULL DEFAULT 'owner',
    chunk_count   INTEGER NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending',
    text          TEXT,
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER NOT NULL,
    PRIMARY KEY (source_id, capability)
);
"""

_SCHEMA = _SOURCES_DDL + """
CREATE INDEX IF NOT EXISTS idx_sources_capability ON sources(capability);
CREATE INDEX IF NOT EXISTS idx_sources_hash ON sources(content_hash);

CREATE TABLE IF NOT EXISTS cursors (
    capability TEXT PRIMARY KEY,
    token      TEXT
);
"""


@dataclass(frozen=True)
class SourceRow:
    source_id: str
    capability: str
    uri: str | None
    title: str | None
    content_hash: str
    chunk_count: int
    status: str


class SqliteLedger:
    def __init__(self, path: str):
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False + a lock: safe for the threaded webhook receiver
        # and any other caller, while still serializing writes (single-writer).
        self.db = sqlite3.connect(str(Path(path).expanduser()), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        with self._lock:
            self.db.executescript(_SCHEMA)
            self._migrate_pk()
            self.db.commit()

    def _migrate_pk(self) -> None:
        """Upgrade a pre-existing `sources` table whose primary key was source_id
        only to the composite (source_id, capability) key."""
        cols = self.db.execute("PRAGMA table_info(sources)").fetchall()
        pk = {c["name"] for c in cols if c["pk"]}
        if pk and pk != {"source_id", "capability"}:
            self.db.executescript(
                "ALTER TABLE sources RENAME TO _sources_old;"
                + _SOURCES_DDL
                + "INSERT OR IGNORE INTO sources SELECT * FROM _sources_old;"
                "DROP TABLE _sources_old;"
            )

    def get(self, source_id: str, capability: str) -> SourceRow | None:
        with self._lock:
            r = self.db.execute("SELECT * FROM sources WHERE source_id=? AND capability=?",
                                (source_id, capability)).fetchone()
        return self._row(r) if r else None

    def is_unchanged(self, source_id: str, content_hash: str, capability: str) -> bool:
        with self._lock:
            r = self.db.execute(
                "SELECT 1 FROM sources WHERE source_id=? AND capability=? AND content_hash=? "
                "AND status='indexed'",
                (source_id, capability, content_hash),
            ).fetchone()
        return r is not None

    def record(self, *, source_id: str, capability: str, uri: str | None, title: str | None,
               content_hash: str, user_id: str, chunk_count: int, status: str,
               text: str | None, now: int) -> None:
        with self._lock:
            self.db.execute(
                """INSERT INTO sources
                     (source_id, capability, uri, title, content_hash, user_id, chunk_count,
                      status, text, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(source_id, capability) DO UPDATE SET
                     uri=excluded.uri, title=excluded.title,
                     content_hash=excluded.content_hash, user_id=excluded.user_id,
                     chunk_count=excluded.chunk_count, status=excluded.status,
                     text=excluded.text, updated_at=excluded.updated_at""",
                (source_id, capability, uri, title, content_hash, user_id, chunk_count,
                 status, text, now, now),
            )
            self.db.commit()

    def delete(self, source_id: str, capability: str) -> SourceRow | None:
        row = self.get(source_id, capability)
        if row:
            with self._lock:
                self.db.execute("DELETE FROM sources WHERE source_id=? AND capability=?",
                                (source_id, capability))
                self.db.commit()
        return row

    def recent(self, limit: int = 20) -> list[SourceRow]:
        with self._lock:
            rows = self.db.execute(
                "SELECT * FROM sources ORDER BY updated_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [self._row(r) for r in rows]

    def find(self, term: str) -> list[SourceRow]:
        like = f"%{term}%"
        with self._lock:
            rows = self.db.execute(
                "SELECT * FROM sources WHERE uri LIKE ? OR title LIKE ? OR source_id=?",
                (like, like, term),
            ).fetchall()
        return [self._row(r) for r in rows]

    def get_cursor(self, capability: str) -> str | None:
        with self._lock:
            r = self.db.execute("SELECT token FROM cursors WHERE capability=?",
                                (capability,)).fetchone()
        return r["token"] if r else None

    def set_cursor(self, capability: str, token: str) -> None:
        with self._lock:
            self.db.execute(
                "INSERT INTO cursors(capability, token) VALUES(?,?) "
                "ON CONFLICT(capability) DO UPDATE SET token=excluded.token",
                (capability, token),
            )
            self.db.commit()

    @staticmethod
    def _row(r: sqlite3.Row) -> SourceRow:
        return SourceRow(
            source_id=r["source_id"], capability=r["capability"], uri=r["uri"],
            title=r["title"], content_hash=r["content_hash"],
            chunk_count=r["chunk_count"], status=r["status"],
        )
