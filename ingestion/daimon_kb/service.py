"""KnowledgeBase: the Facade the agent (via MCP) and CLI talk to. It wires the
deterministic core to the enabled adapters and exposes four verbs — capture,
recall, forget, list_recent — so callers never see vectors, collections, or chunks."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from .adapters.base import AdapterContext
from .adapters.registry import build_enabled_adapters
from .core.config import DaimonKbConfig, load_config
from .core.embed import OllamaEmbedder
from .core.ledger import SqliteLedger
from .core.pipeline import IngestPipeline, IngestResult
from .core.security import SecretRedactor, SSRFGuard
from .core.store import QdrantStore


@dataclass(frozen=True)
class RecallHit:
    title: str
    uri: str | None
    source_type: str
    score: float
    text: str


class KnowledgeBase:
    def __init__(self, cfg: DaimonKbConfig | None = None):
        self.cfg = cfg or load_config()
        self.store = QdrantStore(self.cfg.qdrant.url, self.cfg.qdrant.api_key,
                                 dim=self.cfg.embeddings.dim, model_tag=self.cfg.embeddings.tag)
        self.embedder = OllamaEmbedder(
            base_url=self.cfg.embeddings.base_url, model=self.cfg.embeddings.model,
            dim=self.cfg.embeddings.dim, doc_prefix=self.cfg.embeddings.doc_prefix,
            query_prefix=self.cfg.embeddings.query_prefix,
        )
        self.ledger = SqliteLedger(self.cfg.ledger_path)
        self.pipeline = IngestPipeline(self.cfg, self.store, self.embedder, self.ledger,
                                       SecretRedactor())
        ctx = AdapterContext(
            ssrf=SSRFGuard(allow_private=self.cfg.security.allow_private_networks),
            http=httpx.Client(timeout=30, headers={"user-agent": "daimon-kb/0.1"}),
        )
        self.adapters = build_enabled_adapters(self.cfg, ctx)

    def ensure_collections(self) -> list[str]:
        return [self.store.ensure_collection(name) for name in self.adapters]

    def capture(self, *, url: str | None = None, path: str | None = None,
                text: str | None = None, title: str | None = None,
                tags: tuple[str, ...] = (), user_id: str = "owner") -> IngestResult:
        if url:
            adapter, kw = self._adapter("urls"), {"url": url}
        elif path:
            adapter, kw = self._adapter("files"), {"path": path}
        elif text:
            adapter, kw = self._adapter("chat"), {"text": text, "title": title}
        else:
            raise ValueError("capture needs one of: url, path, text")
        doc = adapter.capture(tags=tags, user_id=user_id, **kw)
        if doc is None:
            raise ValueError("could not extract usable content from the source")
        return self.pipeline.ingest(doc)

    def recall(self, query: str, scope: list[str] | None = None, top_k: int | None = None,
               user_id: str = "owner") -> list[RecallHit]:
        targets = [s for s in (scope or list(self.adapters)) if s in self.adapters]
        if not targets:
            return []
        qvec = self.embedder.embed_query(query)
        r = self.cfg.retrieval
        hits = []
        for source_type in targets:
            hits.extend(self.store.search(
                source_type, qvec, top_k=r.top_k_per_collection,
                score_threshold=r.score_threshold,
                user_filter=[user_id, "owner"] if user_id != "owner" else None,
            ))
        return merge_hits(hits, top_k or r.final_k, r.max_per_source)

    def poll(self, capability: str) -> list[IngestResult]:
        """Run an incremental connector: discover new items, triage+ingest the
        keepers, then let the adapter mark the batch processed. Used by cron."""
        adapter = self._adapter(capability)
        results: list[IngestResult] = []
        processed = []
        for raw in adapter.discover(self.ledger.get_cursor(capability)):
            processed.append(raw)
            doc = adapter.normalize(raw)
            if doc is not None:
                results.append(self.pipeline.ingest(doc))
        adapter.after_ingest(processed)
        return results

    def ingest_text(self, capability: str, text: str, title: str | None = None,
                    url: str | None = None, tags: tuple[str, ...] = (),
                    user_id: str = "owner", meta: dict | None = None) -> IngestResult | None:
        """Ingest arbitrary text into a given collection — used by connectors that do
        their own extraction/enrichment (e.g. AI-categorized feed items)."""
        from .core.document import Document
        from .core.ids import content_hash, source_id_for_text, source_id_for_url

        text = (text or "").strip()
        if not text:
            return None
        sid = source_id_for_url(url) if url else source_id_for_text(text)
        doc = Document(
            source_id=sid, capability=capability,
            title=title or (text[:60] + ("…" if len(text) > 60 else "")),
            text=text, content_hash=content_hash(text), uri=url,
            tags=tuple(tags), user_id=user_id, meta=meta or {})
        return self.pipeline.ingest(doc)

    def ingest_push(self, capability: str, payload: dict) -> IngestResult | None:
        """Ingest a single pushed item (e.g. from the webhook receiver)."""
        adapter = self._adapter(capability)
        from .core.document import RawItem

        doc = adapter.normalize(RawItem(source_id="push", payload=payload))
        return self.pipeline.ingest(doc) if doc is not None else None

    def forget(self, identifier: str) -> list[str]:
        rows = self.ledger.find(identifier)
        forgotten = []
        for row in rows:
            self.store.delete_by_source(row.capability, row.source_id)
            self.ledger.delete(row.source_id, row.capability)
            forgotten.append(row.title or row.source_id)
        return forgotten

    def list_recent(self, limit: int = 20) -> list[tuple[str, str | None, str]]:
        return [(r.title or r.source_id, r.uri, r.capability) for r in self.ledger.recent(limit)]

    def cluster_sources(self, capability: str, min_score: float = 0.62,
                        neighbors: int = 6, limit: int = 400) -> list[list[dict]]:
        """Group a collection's sources into semantic clusters: connected components
        over edges between each source and its nearest neighbours. Returns lists of
        source dicts (title, uri, tags, summary), largest cluster first."""
        sources = self.store.list_sources(capability, limit=limit)
        by_id = {s["source_id"]: s for s in sources}
        parent = {sid: sid for sid in by_id}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for sid in list(by_id):
            vec = self.store.representative_vector(capability, sid)
            if not vec:
                continue
            for h in self.store.search(capability, vec, top_k=neighbors + 1, score_threshold=min_score):
                if h.source_id != sid and h.source_id in parent:
                    parent[find(sid)] = find(h.source_id)

        clusters: dict[str, list[dict]] = {}
        for sid in by_id:
            clusters.setdefault(find(sid), []).append(by_id[sid])
        return sorted(clusters.values(), key=lambda c: -len(c))

    def graph(self, neighbors: int = 4, min_score: float = 0.6, limit: int = 400) -> dict:
        """Build a knowledge graph: a node per source, edges to each source's nearest
        semantic neighbours (across all enabled types, so a url links to a related
        feed item). Undirected, deduped, cross_type flagged for styling."""
        rows = self.ledger.recent(limit)
        # Node id is qualified by capability: the same URL can exist as both a `urls`
        # and a `feeds` source (distinct ledger rows), and they must stay distinct nodes.
        def nid(capability: str, source_id: str) -> str:
            return f"{capability}:{source_id}"

        node_ids = {nid(r.capability, r.source_id) for r in rows}
        nodes = [{"id": nid(r.capability, r.source_id), "title": r.title or r.source_id,
                  "type": r.capability, "uri": r.uri} for r in rows]
        links, seen = [], set()
        for r in rows:
            src = nid(r.capability, r.source_id)
            vec = self.store.representative_vector(r.capability, r.source_id)
            if not vec:
                continue
            for cap in self.adapters:  # hits from collection `cap` have that capability
                for h in self.store.search(cap, vec, top_k=neighbors + 1, score_threshold=min_score):
                    tgt = nid(cap, h.source_id)
                    if tgt == src or tgt not in node_ids:
                        continue
                    key = tuple(sorted((src, tgt)))
                    if key in seen:
                        continue
                    seen.add(key)
                    links.append({"source": src, "target": tgt, "score": round(h.score, 3),
                                  "cross_type": cap != r.capability})
        return {"nodes": nodes, "links": links}

    def _adapter(self, name: str):
        if name not in self.adapters:
            raise ValueError(f"the {name!r} capability is not enabled")
        return self.adapters[name]


def merge_hits(hits, final_k: int, max_per_source: int) -> list[RecallHit]:
    """Rank fan-out search hits: drop exact duplicate chunks and near-duplicate
    documents from *other* sources, allow up to max_per_source chunks per document,
    and cap to final_k."""
    hits.sort(key=lambda h: h.score, reverse=True)
    seen_chunk: set[tuple[str, int]] = set()
    doc_owner: dict[str, str] = {}             # content_hash -> first source_id seen
    per_source: dict[str, int] = {}
    out: list[RecallHit] = []
    for h in hits:
        chunk_key = (h.source_id, h.chunk_index)
        if chunk_key in seen_chunk:
            continue
        ch = h.payload.get("content_hash", "")
        if ch and doc_owner.get(ch, h.source_id) != h.source_id:
            continue  # same content from a different source — a near-duplicate
        if per_source.get(h.source_id, 0) >= max_per_source:
            continue
        seen_chunk.add(chunk_key)
        doc_owner.setdefault(ch, h.source_id)
        per_source[h.source_id] = per_source.get(h.source_id, 0) + 1
        out.append(RecallHit(h.title, h.uri, h.source_type, round(h.score, 4), h.text))
        if len(out) >= final_k:
            break
    return out

