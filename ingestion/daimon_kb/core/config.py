"""Config schema + loader. The `capabilities` map is the only place a source type
is turned on; an enabled capability with no registered adapter is a hard error
(fail-closed, matching the project's security stance)."""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_ENV_RE = re.compile(r"\$\{([^}]+)\}")


class QdrantCfg(BaseModel):
    url: str = "http://qdrant:6333"
    api_key: str | None = None


class EmbedCfg(BaseModel):
    base_url: str = "http://ollama:11434"
    model: str = "nomic-embed-text"
    tag: str = "nomic"
    dim: int = 768
    doc_prefix: str = "search_document: "
    query_prefix: str = "search_query: "


class ChunkCfg(BaseModel):
    target_chars: int = 1100
    overlap_chars: int = 150


class RetrievalCfg(BaseModel):
    top_k_per_collection: int = 20
    final_k: int = 8
    score_threshold: float = 0.55
    max_per_source: int = 3


class SecurityCfg(BaseModel):
    redact_secrets: bool = True
    allow_private_networks: bool = False


class Capability(BaseModel):
    enabled: bool = False
    settings: dict[str, Any] = Field(default_factory=dict)


class DaimonKbConfig(BaseModel):
    ledger_path: str = "~/.hermes/daimon_kb/ledger.db"
    qdrant: QdrantCfg = QdrantCfg()
    embeddings: EmbedCfg = EmbedCfg()
    chunk: ChunkCfg = ChunkCfg()
    retrieval: RetrievalCfg = RetrievalCfg()
    security: SecurityCfg = SecurityCfg()
    capabilities: dict[str, Capability] = Field(default_factory=dict)

    def enabled_capabilities(self) -> list[str]:
        return [name for name, c in self.capabilities.items() if c.enabled]


def _expand(obj: Any) -> Any:
    if isinstance(obj, str):
        return _ENV_RE.sub(lambda m: os.environ.get(m.group(1), ""), obj)
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    return obj


def load_config(path: str | None = None) -> DaimonKbConfig:
    """Load from an explicit path, $DAIMON_KB_CONFIG, or ~/.hermes/daimon_kb.yaml.
    Falls back to defaults if no file exists. Env vars are expanded, and
    QDRANT_API_KEY is read from the environment when not set in the file."""
    candidate = path or os.environ.get("DAIMON_KB_CONFIG") or "~/.hermes/daimon_kb.yaml"
    p = Path(candidate).expanduser()
    raw: dict[str, Any] = {}
    if p.exists():
        raw = _expand(yaml.safe_load(p.read_text()) or {})
        if isinstance(raw, dict) and "daimon_kb" in raw:
            raw = raw["daimon_kb"]
    cfg = DaimonKbConfig(**raw)
    if not cfg.qdrant.api_key:
        cfg.qdrant.api_key = os.environ.get("QDRANT_API_KEY")
    return cfg
