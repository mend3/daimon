"""The ingestion pipeline (Template Method): a fixed skeleton — dedup → redact →
chunk → embed → upsert → record — shared by every source. Adapters supply the
Document; the model never enters this path."""
from __future__ import annotations

import time
from dataclasses import dataclass

from .chunk import chunk_text
from .config import EllaKbConfig
from .document import Document
from .embed import OllamaEmbedder
from .ledger import SqliteLedger
from .security import SecretRedactor
from .store import QdrantStore


@dataclass(frozen=True)
class IngestResult:
    source_id: str
    capability: str
    title: str
    chunk_count: int
    deduped: bool


class IngestPipeline:
    def __init__(self, cfg: EllaKbConfig, store: QdrantStore, embedder: OllamaEmbedder,
                 ledger: SqliteLedger, redactor: SecretRedactor | None = None):
        self.cfg = cfg
        self.store = store
        self.embedder = embedder
        self.ledger = ledger
        self.redactor = redactor or SecretRedactor()

    def ingest(self, doc: Document) -> IngestResult:
        if self.ledger.is_unchanged(doc.source_id, doc.content_hash, doc.capability):
            return IngestResult(doc.source_id, doc.capability, doc.title, 0, deduped=True)

        text = self.redactor.redact(doc.text) if self.cfg.security.redact_secrets else doc.text
        chunks = chunk_text(text, self.cfg.chunk.target_chars, self.cfg.chunk.overlap_chars)
        if not chunks:
            raise ValueError(f"nothing to ingest for {doc.source_id} (empty text)")

        self.store.ensure_collection(doc.capability)
        # Replace any prior version: delete old points, then upsert fresh (no orphans).
        self.store.delete_by_source(doc.capability, doc.source_id)

        vectors = self.embedder.embed_documents(chunks)
        now = int(time.time())
        payload_base = {
            "source_id": doc.source_id,
            "source_type": doc.capability,
            "title": doc.title,
            "uri": doc.uri,
            "tags": list(doc.tags),
            "summary": doc.summary,
            "user_id": doc.user_id,
            "content_hash": doc.content_hash,
            "embed_model": self.cfg.embeddings.model,
            "created_at": now,
            **{f"x_{k}": v for k, v in doc.meta.items()},
        }
        n = self.store.upsert_chunks(doc.capability, doc.source_id, chunks, vectors, payload_base)
        self.ledger.record(
            source_id=doc.source_id, capability=doc.capability, uri=doc.uri,
            title=doc.title, content_hash=doc.content_hash, user_id=doc.user_id,
            chunk_count=n, status="indexed", text=text, now=now,
        )
        return IngestResult(doc.source_id, doc.capability, doc.title, n, deduped=False)
