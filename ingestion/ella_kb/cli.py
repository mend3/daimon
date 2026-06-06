"""`ella-kb` command line — init collections, capture, recall, forget, recent.
Handy for setup and debugging; the agent uses the MCP server, not this."""
from __future__ import annotations

import argparse
import sys

from .service import KnowledgeBase


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ella-kb", description="Ella's knowledge base")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create collections for enabled capabilities")

    cap = sub.add_parser("capture", help="ingest a url, file, or note")
    g = cap.add_mutually_exclusive_group(required=True)
    g.add_argument("--url")
    g.add_argument("--path")
    g.add_argument("--text")
    cap.add_argument("--title")
    cap.add_argument("--tags", default="")

    rec = sub.add_parser("recall", help="semantic search")
    rec.add_argument("query")
    rec.add_argument("--scope", default="", help="comma-separated source types")
    rec.add_argument("--top-k", type=int)

    forget = sub.add_parser("forget", help="delete a source by url/title/id")
    forget.add_argument("identifier")

    r = sub.add_parser("recent", help="list recently captured sources")
    r.add_argument("--limit", type=int, default=20)

    poll = sub.add_parser("poll", help="run an incremental connector (e.g. feeds)")
    poll.add_argument("capability")

    sub.add_parser("webhook-serve", help="run the inbound webhook receiver")

    args = parser.parse_args(argv)

    if args.cmd == "webhook-serve":
        from .apps.webhook_receiver import main as serve
        serve()
        return 0

    kb = KnowledgeBase()

    if args.cmd == "init":
        names = kb.ensure_collections()
        print("collections:", ", ".join(names) or "(none — no capabilities enabled)")
    elif args.cmd == "capture":
        tags = tuple(t.strip() for t in args.tags.split(",") if t.strip())
        res = kb.capture(url=args.url, path=args.path, text=args.text, title=args.title, tags=tags)
        print(f"{'deduped' if res.deduped else 'indexed'}: {res.title} "
              f"({res.capability}, {res.chunk_count} chunks)")
    elif args.cmd == "recall":
        scope = [s.strip() for s in args.scope.split(",") if s.strip()] or None
        hits = kb.recall(args.query, scope=scope, top_k=args.top_k)
        if not hits:
            print("(nothing relevant found)")
        for i, h in enumerate(hits, 1):
            loc = h.uri or f"({h.source_type})"
            print(f"[{i}] {h.score}  {h.title} — {loc}\n    {h.text[:160].strip()}…")
    elif args.cmd == "forget":
        gone = kb.forget(args.identifier)
        print("forgot:", ", ".join(gone) if gone else "(nothing matched)")
    elif args.cmd == "recent":
        for title, uri, cap in kb.list_recent(args.limit):
            print(f"- {title} [{cap}] {uri or ''}".rstrip())
    elif args.cmd == "poll":
        results = kb.poll(args.capability)
        fresh = [r for r in results if not r.deduped]
        print(f"{len(fresh)} new, {len(results) - len(fresh)} already known")
        for r in fresh:
            print(f"- {r.title} ({r.chunk_count} passages)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
