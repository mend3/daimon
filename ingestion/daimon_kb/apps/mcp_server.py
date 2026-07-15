"""MCP stdio server — the Facade exposed to Daimon. Four tools, all high-level:
kb_capture, kb_recall, kb_forget, kb_list_recent. The language model never sees
embeddings, collections, or chunks; it only states intent."""
from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from ..service import KnowledgeBase

mcp = FastMCP("daimon-kb")
_kb: KnowledgeBase | None = None


def kb() -> KnowledgeBase:
    global _kb
    if _kb is None:
        _kb = KnowledgeBase()
        _kb.ensure_collections()
    return _kb


@mcp.tool()
def kb_capture(url: str | None = None, path: str | None = None, text: str | None = None,
               title: str | None = None, tags: list[str] | None = None) -> str:
    """Save something to long-term memory: a web link (url), a local file (path), or
    a note (text). Returns a short confirmation."""
    res = kb().capture(url=url, path=path, text=text, title=title, tags=tuple(tags or ()))
    if res.deduped:
        return f"Already saved: {res.title}"
    return f"Saved {res.title} ({res.chunk_count} passages)."


@mcp.tool()
def kb_recall(query: str, scope: list[str] | None = None, top_k: int | None = None) -> str:
    """Recall saved knowledge by meaning. Optionally limit `scope` to source types
    (files, urls, feeds, webhook, chat). Returns ranked, cited passages."""
    hits = kb().recall(query, scope=scope, top_k=top_k)
    if not hits:
        return "Nothing relevant in memory."
    lines = []
    for i, h in enumerate(hits, 1):
        cite = h.uri or f"({h.source_type})"
        lines.append(f"[{i}] {h.title} — {cite}\n{h.text.strip()}")
    return "\n\n".join(lines)


@mcp.tool()
def kb_forget(identifier: str) -> str:
    """Forget a saved source, matched by url, title, or id."""
    gone = kb().forget(identifier)
    return ("Forgot: " + ", ".join(gone)) if gone else "Nothing matched."


@mcp.tool()
def kb_list_recent(limit: int = 20) -> str:
    """List recently saved sources."""
    items = kb().list_recent(limit)
    if not items:
        return "Nothing saved yet."
    return "\n".join(f"- {t} [{c}] {u or ''}".rstrip() for t, u, c in items)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
