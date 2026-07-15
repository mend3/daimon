"""URL adapter: fetch a web page (SSRF-guarded) and extract its main content."""
from __future__ import annotations

from typing import Any

import httpx
import trafilatura

from ..core.document import Document, RawItem
from ..core.ids import canonical_url, content_hash, source_id_for_url
from ..core.security import SSRFError
from .base import SourceAdapter
from .registry import register


@register
class UrlAdapter(SourceAdapter):
    capability = "urls"

    @property
    def supports_incremental(self) -> bool:
        return True

    def capture(self, *, url: str, tags: tuple[str, ...] = (), user_id: str = "owner",
                **_: Any) -> Document | None:
        return self.normalize(RawItem(source_id=source_id_for_url(url), payload={"url": url},
                                      meta={"tags": tags, "user_id": user_id}))

    def fetch(self, item: RawItem) -> RawItem:
        url = item.payload["url"]
        timeout = float(self.settings.get("timeout_s", 20))
        r = self._get_guarded(url, timeout)
        r.raise_for_status()
        return RawItem(source_id=item.source_id, payload={"url": url, "html": r.text},
                       etag=r.headers.get("etag"), meta=item.meta)

    def _get_guarded(self, url: str, timeout: float, max_redirects: int = 5):
        """Follow redirects manually, checking each hop against the SSRF guard
        *before* contacting it — so a public URL can't redirect into the private
        network. (follow_redirects=True would fetch the final hop first.)"""
        for _ in range(max_redirects + 1):
            self.ctx.ssrf.check(url)
            r = self.ctx.http.get(url, timeout=timeout, follow_redirects=False)
            if not r.is_redirect:
                return r
            loc = r.headers.get("location")
            if not loc:
                return r
            url = str(httpx.URL(str(r.url)).join(loc))
        raise SSRFError("too many redirects")

    def normalize(self, item: RawItem) -> Document | None:
        if "html" not in (item.payload or {}):
            item = self.fetch(item)
        url = item.payload["url"]
        html = item.payload["html"]
        text = trafilatura.extract(html, include_comments=False, include_tables=True) or ""
        if len(text.strip()) < 200:
            return None  # thin/JS-heavy page — let the agent retry via the browser
        title = (trafilatura.extract_metadata(html).title if trafilatura.extract_metadata(html) else None) or url
        meta = item.meta or {}
        return Document(
            source_id=item.source_id, capability=self.capability, title=title, text=text,
            content_hash=content_hash(text), uri=canonical_url(url),
            tags=tuple(meta.get("tags", ())), user_id=meta.get("user_id", "owner"),
            incremental_token=item.etag,
        )
