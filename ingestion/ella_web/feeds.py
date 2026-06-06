"""Feeds module backend: a thin Miniflux client plus an AI pipeline that reads new
items, lets the model categorize them into topics, and injects the kept ones into the
RAG knowledge base so they become available to Ella."""
from __future__ import annotations

import json
import os
import re

import httpx

from ella_flow.chat_client import OllamaChat
from ella_kb.service import KnowledgeBase

_HTML = re.compile(r"<[^>]+>")
_JSON = re.compile(r"\{.*\}", re.S)

_CATEGORIZE = """You are organizing a feed item for a personal knowledge base.
Reply with ONLY JSON, no prose:
{{"keep": true|false, "topic": "<short Title Case topic, 1-3 words>", "summary": "<one or two sentences>"}}
Set keep=false only for spam, navigation, or empty content.

Title: {title}
Content: {content}"""


class MinifluxClient:
    def __init__(self) -> None:
        self.base = os.environ.get("MINIFLUX_URL", "").rstrip("/")
        self.auth = (os.environ.get("MINIFLUX_USERNAME", ""), os.environ.get("MINIFLUX_PASSWORD", ""))
        self._http = httpx.Client(timeout=20)

    def _ok(self) -> bool:
        return bool(self.base and self.auth[0] and self.auth[1])

    def feeds(self) -> list[dict]:
        if not self._ok():
            return []
        r = self._http.get(f"{self.base}/v1/feeds", auth=self.auth)
        r.raise_for_status()
        return [{"id": f["id"], "title": f["title"], "site_url": f.get("site_url"),
                 "category": (f.get("category") or {}).get("title")} for f in r.json()]

    def categories(self) -> list[dict]:
        r = self._http.get(f"{self.base}/v1/categories", auth=self.auth)
        r.raise_for_status()
        return r.json()

    def unread(self, limit: int = 20) -> list[dict]:
        r = self._http.get(f"{self.base}/v1/entries", auth=self.auth,
                           params={"status": "unread", "limit": limit,
                                   "order": "published_at", "direction": "desc"})
        r.raise_for_status()
        return r.json().get("entries", [])

    def subscribe(self, feed_url: str) -> dict:
        cats = self.categories()
        cat_id = cats[0]["id"] if cats else 1
        r = self._http.post(f"{self.base}/v1/feeds", auth=self.auth,
                            json={"feed_url": feed_url, "category_id": cat_id})
        r.raise_for_status()
        fid = r.json().get("feed_id")
        self._http.put(f"{self.base}/v1/feeds/{fid}/refresh", auth=self.auth)
        return {"feed_id": fid}

    def mark_read(self, ids: list[int]) -> None:
        if ids:
            self._http.put(f"{self.base}/v1/entries", auth=self.auth,
                          json={"entry_ids": ids, "status": "read"}).raise_for_status()


def _categorize(chat: OllamaChat, title: str, content: str) -> dict:
    prompt = _CATEGORIZE.format(title=title, content=content[:2500])
    raw = chat.complete(prompt, system="You categorize text and reply only in JSON.")
    m = _JSON.search(raw)
    try:
        data = json.loads(m.group(0)) if m else {}
    except Exception:
        data = {}
    return {"keep": bool(data.get("keep", True)),
            "topic": (data.get("topic") or "Uncategorized").strip()[:40],
            "summary": (data.get("summary") or "").strip()}


def process(limit: int = 15) -> dict:
    """Pull unread items, AI-categorize each, ingest the keepers into the RAG as
    `feeds` (topic as a tag), and mark them read. Returns what was processed."""
    mf = MinifluxClient()
    kb = KnowledgeBase()
    chat = OllamaChat()
    processed, processed_ids = [], []
    for e in mf.unread(limit):
        processed_ids.append(e["id"])
        text = _HTML.sub(" ", e.get("content", "")).strip()
        title = e.get("title") or e.get("url")
        if len(text) < 80:
            continue
        cat = _categorize(chat, title, text)
        if not cat["keep"]:
            continue
        kb.ingest_text("feeds", text=text, title=title, url=e.get("url"),
                       tags=(cat["topic"],),
                       meta={"topic": cat["topic"], "summary": cat["summary"],
                             "feed": (e.get("feed") or {}).get("title", "")})
        processed.append({"title": title, "url": e.get("url"), "topic": cat["topic"],
                          "summary": cat["summary"]})
    mf.mark_read(processed_ids)
    return {"processed": len(processed), "skipped": len(processed_ids) - len(processed),
            "items": processed}


def _label_cluster(chat: OllamaChat, topics: list[str]) -> str:
    raw = chat.complete(
        "Give a 1-3 word Title Case theme that best summarizes this group of topics. "
        "Reply with ONLY the theme.\n\nTopics: " + ", ".join(topics),
        system="You name a group of related topics with a short theme.")
    return raw.strip().strip('"').splitlines()[0][:40] or topics[0]


def clusters() -> dict:
    """Group ingested feed items into semantic themes (clusters of related items),
    each named by the model — so the view stays dense and meaningful as per-item
    topics proliferate."""
    from collections import Counter

    kb = KnowledgeBase()
    chat = OllamaChat()
    out = []
    for members in kb.cluster_sources("feeds"):
        topics = [(m.get("tags") or ["Uncategorized"])[0] or "Uncategorized" for m in members]
        theme = _label_cluster(chat, topics) if len(members) > 1 else topics[0]
        out.append({
            "theme": theme, "size": len(members),
            "items": [{"title": m.get("title"), "uri": m.get("uri"),
                       "summary": m.get("summary"), "topic": (m.get("tags") or [""])[0]}
                      for m in members],
        })
    return {"clusters": sorted(out, key=lambda c: -c["size"])}
