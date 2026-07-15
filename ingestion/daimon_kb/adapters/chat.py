"""Chat adapter: saves free-text the user wants kept (a note typed in conversation)
and, incrementally, conversation history. Manual notes are the Phase 1 path."""
from __future__ import annotations

from typing import Any

from ..core.document import Document, RawItem
from ..core.ids import content_hash, source_id_for_text
from .base import SourceAdapter
from .registry import register


@register
class ChatAdapter(SourceAdapter):
    capability = "chat"

    def capture(self, *, text: str, title: str | None = None, tags: tuple[str, ...] = (),
                user_id: str = "owner", **_: Any) -> Document | None:
        text = text.strip()
        if not text:
            return None
        return self.normalize(RawItem(source_id=source_id_for_text(text),
                                      payload={"text": text, "title": title},
                                      meta={"tags": tags, "user_id": user_id, "role": "note"}))

    def normalize(self, item: RawItem) -> Document | None:
        text = item.payload["text"].strip()
        if not text:
            return None
        meta = item.meta or {}
        title = item.payload.get("title") or (text[:60] + ("…" if len(text) > 60 else ""))
        return Document(
            source_id=item.source_id, capability=self.capability, title=title, text=text,
            content_hash=content_hash(text), uri=None,
            tags=tuple(meta.get("tags", ())), user_id=meta.get("user_id", "owner"),
            meta={"role": meta.get("role", "note")},
        )
