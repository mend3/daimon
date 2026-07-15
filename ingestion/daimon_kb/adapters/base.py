"""The adapter contract (Adapter pattern). An adapter wraps one external source
into Documents; everything downstream (chunk/embed/upsert/ledger) is shared core.
Adapters never touch Qdrant, embeddings, or the ledger directly."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Iterator

import httpx

from ..core.document import Document, RawItem
from ..core.security import SSRFGuard


@dataclass
class AdapterContext:
    """Read-only handles injected into every adapter."""

    ssrf: SSRFGuard
    http: httpx.Client


class SourceAdapter(ABC):
    capability: str = ""  # unique name; == enabled key == collection suffix

    def __init__(self, settings: dict[str, Any], ctx: AdapterContext):
        self.settings = settings
        self.ctx = ctx

    @property
    def supports_incremental(self) -> bool:
        return False

    @property
    def push_driven(self) -> bool:
        return False

    def discover(self, since: str | None) -> Iterator[RawItem]:
        """Enumerate candidate items (incremental adapters honor `since`)."""
        return iter(())

    def fetch(self, item: RawItem) -> RawItem:
        """Materialize content if discover() didn't already."""
        return item

    @abstractmethod
    def normalize(self, item: RawItem) -> Document | None:
        """Clean a RawItem into a Document, or None to skip."""

    def capture(self, **kwargs: Any) -> Document | None:
        """Direct, user-initiated capture (e.g. /save). Default: not supported."""
        raise NotImplementedError(f"{self.capability} does not support direct capture")

    def after_ingest(self, items: list[RawItem]) -> None:
        """Hook run after a poll batch is ingested (e.g. mark feed entries read)."""
        return None

    def healthcheck(self) -> None:
        return None
