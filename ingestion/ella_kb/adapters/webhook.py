"""Webhook adapter (example connector): push-driven ingestion. The receiver app
validates an HMAC signature and hands a JSON payload here to normalize. Lets any
external service drop knowledge into Ella's memory."""
from __future__ import annotations

from typing import Any

from ..core.document import Document, RawItem
from ..core.ids import content_hash, source_id_for_text, source_id_for_url
from .base import SourceAdapter
from .registry import register


@register
class WebhookAdapter(SourceAdapter):
    capability = "webhook"

    @property
    def push_driven(self) -> bool:
        return True

    def normalize(self, item: RawItem) -> Document | None:
        p = item.payload or {}
        text = (p.get("text") or "").strip()
        if not text:
            return None
        url = p.get("url")
        source_id = source_id_for_url(url) if url else source_id_for_text(text)
        title = p.get("title") or (text[:60] + ("…" if len(text) > 60 else ""))
        return Document(
            source_id=source_id, capability=self.capability, title=title, text=text,
            content_hash=content_hash(text), uri=url,
            tags=tuple(p.get("tags", ())),
            meta={"source_app": p.get("source_app", ""), "event_type": p.get("event_type", "")},
        )

    def build_raw(self, payload: dict[str, Any]) -> RawItem:
        return RawItem(source_id="webhook:pending", payload=payload)
