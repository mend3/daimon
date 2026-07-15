"""The data contract every adapter normalizes into."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class RawItem:
    """What an adapter's discover()/fetch() hand around before normalization."""

    source_id: str
    payload: Any = None
    fetched_at: datetime = field(default_factory=utcnow)
    etag: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Document:
    """A normalized, ready-to-ingest unit. `source_id` and `content_hash` drive
    idempotency and dedup; `capability` selects the target collection."""

    source_id: str
    capability: str
    title: str
    text: str
    content_hash: str
    uri: str | None = None
    tags: tuple[str, ...] = ()
    summary: str | None = None
    user_id: str = "owner"
    created_at: datetime | None = None
    fetched_at: datetime = field(default_factory=utcnow)
    incremental_token: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Chunk:
    document_source_id: str
    chunk_index: int
    text: str
