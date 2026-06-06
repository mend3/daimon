"""Qdrant access: one collection per source type, idempotent ensure/upsert,
filtered search and delete. Collection names carry the embedding signature
(kb_<type>__nomic768) so a model change builds new collections beside the old."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from .ids import point_id

_COMMON_KEYWORD_INDEXES = ("source_id", "source_type", "content_hash", "user_id")
_COMMON_TEXT_INDEXES = ("tags",)


@dataclass(frozen=True)
class SearchHit:
    score: float
    source_id: str
    source_type: str
    title: str
    text: str
    uri: str | None
    chunk_index: int
    payload: dict[str, Any]


def collection_name(source_type: str, model_tag: str = "nomic", dim: int = 768) -> str:
    return f"kb_{source_type}__{model_tag}{dim}"


class QdrantStore:
    def __init__(self, url: str, api_key: str | None, dim: int = 768, model_tag: str = "nomic"):
        self.client = QdrantClient(url=url, api_key=api_key or None, timeout=30)
        self.dim = dim
        self.model_tag = model_tag

    def collection_for(self, source_type: str) -> str:
        return collection_name(source_type, self.model_tag, self.dim)

    def ensure_collection(self, source_type: str) -> str:
        name = self.collection_for(source_type)
        if not self.client.collection_exists(name):
            self.client.create_collection(
                collection_name=name,
                vectors_config=qm.VectorParams(size=self.dim, distance=qm.Distance.COSINE),
            )
        for field in _COMMON_KEYWORD_INDEXES:
            self._ensure_index(name, field, qm.PayloadSchemaType.KEYWORD)
        for field in _COMMON_TEXT_INDEXES:
            self._ensure_index(name, field, qm.PayloadSchemaType.KEYWORD)
        self._ensure_index(name, "created_at", qm.PayloadSchemaType.INTEGER)
        return name

    def upsert_chunks(self, source_type: str, source_id: str, chunks: list[str],
                      vectors: list[list[float]], payload_base: dict[str, Any]) -> int:
        name = self.collection_for(source_type)
        points = [
            qm.PointStruct(
                id=point_id(source_id, i),
                vector=vec,
                payload={**payload_base, "chunk_index": i, "text": chunk},
            )
            for i, (chunk, vec) in enumerate(zip(chunks, vectors))
        ]
        self.client.upsert(collection_name=name, points=points)
        return len(points)

    def representative_vector(self, source_type: str, source_id: str) -> list[float] | None:
        """The first chunk's vector — a stand-in for the whole document, used to
        relate sources to each other in the knowledge graph."""
        name = self.collection_for(source_type)
        if not self.client.collection_exists(name):
            return None
        res = self.client.retrieve(collection_name=name, ids=[point_id(source_id, 0)],
                                   with_vectors=True)
        if res and res[0].vector:
            return res[0].vector
        return None

    def delete_by_source(self, source_type: str, source_id: str) -> None:
        name = self.collection_for(source_type)
        self.client.delete(
            collection_name=name,
            points_selector=qm.FilterSelector(
                filter=qm.Filter(must=[qm.FieldCondition(key="source_id",
                                                         match=qm.MatchValue(value=source_id))])
            ),
        )

    def search(self, source_type: str, vector: list[float], top_k: int,
               score_threshold: float | None, user_filter: list[str] | None = None) -> list[SearchHit]:
        name = self.collection_for(source_type)
        if not self.client.collection_exists(name):
            return []
        qfilter = None
        if user_filter:
            qfilter = qm.Filter(should=[
                qm.FieldCondition(key="user_id", match=qm.MatchValue(value=u)) for u in user_filter
            ])
        res = self.client.query_points(
            collection_name=name,
            query=vector,
            limit=top_k,
            score_threshold=score_threshold,
            with_payload=True,
            query_filter=qfilter,
        )
        return [self._to_hit(p) for p in res.points]

    def _ensure_index(self, name: str, field: str, schema: qm.PayloadSchemaType) -> None:
        try:
            self.client.create_payload_index(collection_name=name, field_name=field, field_schema=schema)
        except Exception:
            pass  # already exists / benign — idempotent ensure

    @staticmethod
    def _to_hit(p) -> SearchHit:
        pl = p.payload or {}
        return SearchHit(
            score=p.score,
            source_id=pl.get("source_id", ""),
            source_type=pl.get("source_type", ""),
            title=pl.get("title", ""),
            text=pl.get("text", ""),
            uri=pl.get("uri"),
            chunk_index=pl.get("chunk_index", 0),
            payload=pl,
        )
