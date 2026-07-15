"""Feeds adapter (example connector): pulls unread entries from a self-hosted
Miniflux, keyword-triages them, and hands the keepers to the core pipeline. Marks
entries read afterward so the unread queue is the cursor. Miniflux only fetches;
Daimon decides what's worth keeping."""
from __future__ import annotations

import os
from typing import Any, Iterator

from ..core.document import Document, RawItem
from ..core.ids import canonical_url, content_hash, source_id_for_url
from .base import SourceAdapter
from .registry import register


@register
class FeedAdapter(SourceAdapter):
    capability = "feeds"

    @property
    def supports_incremental(self) -> bool:
        return True

    def _conf(self) -> tuple[str, tuple[str, str]]:
        url = self.settings.get("url") or os.environ.get("MINIFLUX_URL", "")
        user = self.settings.get("username") or os.environ.get("MINIFLUX_USERNAME", "")
        pw = self.settings.get("password") or os.environ.get("MINIFLUX_PASSWORD", "")
        if not (url and user and pw):
            raise RuntimeError("feeds: set MINIFLUX_URL/USERNAME/PASSWORD (env or settings)")
        return url.rstrip("/"), (user, pw)

    def discover(self, since: str | None) -> Iterator[RawItem]:
        base, auth = self._conf()
        limit = int(self.settings.get("batch_limit", 50))
        r = self.ctx.http.get(f"{base}/v1/entries", auth=auth,
                              params={"status": "unread", "limit": limit,
                                      "order": "published_at", "direction": "desc"})
        r.raise_for_status()
        for e in r.json().get("entries", []):
            yield RawItem(
                source_id=source_id_for_url(e["url"]),
                payload=e,
                meta={"entry_id": e["id"]},
            )

    def normalize(self, item: RawItem) -> Document | None:
        e = item.payload
        text = _strip_html(e.get("content", ""))
        title = e.get("title") or e.get("url")
        if not _passes_triage(f"{title}\n{text}", self.settings):
            return None
        if len(text.strip()) < 80:
            return None
        feed = e.get("feed", {}) or {}
        return Document(
            source_id=item.source_id, capability=self.capability, title=title, text=text,
            content_hash=content_hash(text), uri=canonical_url(e["url"]),
            tags=tuple(self.settings.get("tags", ())),
            meta={"feed": feed.get("title", ""), "published_at": e.get("published_at", "")},
        )

    def after_ingest(self, items: list[RawItem]) -> None:
        ids = [it.meta["entry_id"] for it in items if it.meta.get("entry_id")]
        if not ids:
            return
        base, auth = self._conf()
        self.ctx.http.put(f"{base}/v1/entries", auth=auth,
                          json={"entry_ids": ids, "status": "read"}).raise_for_status()


def _strip_html(html: str) -> str:
    import re
    text = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", html, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _passes_triage(text: str, settings: dict[str, Any]) -> bool:
    low = text.lower()
    include = [k.lower() for k in settings.get("include", [])]
    exclude = [k.lower() for k in settings.get("exclude", [])]
    if exclude and any(k in low for k in exclude):
        return False
    if include and not any(k in low for k in include):
        return False
    return True
