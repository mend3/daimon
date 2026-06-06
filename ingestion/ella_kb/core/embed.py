"""Embeddings via the local Ollama endpoint. nomic-embed-text needs task prefixes
(`search_document:` when storing, `search_query:` when querying); store and query
MUST share the model+prefixes or cosine similarity is meaningless. This is the one
reason the official mcp-server-qdrant (FastEmbed-only) isn't used."""
from __future__ import annotations

import httpx


class EmbedError(RuntimeError):
    pass


class OllamaEmbedder:
    def __init__(
        self,
        base_url: str = "http://host.docker.internal:11434",
        model: str = "nomic-embed-text",
        dim: int = 768,
        doc_prefix: str = "search_document: ",
        query_prefix: str = "search_query: ",
        timeout: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.dim = dim
        self.doc_prefix = doc_prefix
        self.query_prefix = query_prefix
        self._client = httpx.Client(timeout=timeout)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed([self.doc_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._embed([self.query_prefix + text])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        try:
            r = self._client.post(
                f"{self.base_url}/api/embed",
                json={"model": self.model, "input": inputs},
            )
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPError as e:
            raise EmbedError(f"embedding request failed: {e}") from e
        vecs = data.get("embeddings") or ([data["embedding"]] if "embedding" in data else None)
        if not vecs or len(vecs) != len(inputs):
            raise EmbedError(f"unexpected embedding response shape: {list(data)}")
        return vecs

    def close(self) -> None:
        self._client.close()
