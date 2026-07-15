"""Deterministic identity: stable source IDs, content hashes, and point IDs.

Re-ingesting the same content overwrites the same Qdrant points (idempotent) and a
re-poll that yields unchanged text is skipped by content hash."""
from __future__ import annotations

import hashlib
import re
import uuid
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

_NAMESPACE = uuid.UUID("b6e3f1a2-0c4d-5e6f-8a9b-0c1d2e3f4a5b")
_TRACKING = re.compile(r"^(utm_|fbclid$|gclid$|mc_eid$|ref$)", re.I)


def canonical_url(url: str) -> str:
    """Normalize so trivially different URLs share one source_id: lowercase host,
    drop fragments, strip tracking params, drop a trailing slash."""
    s = urlsplit(url.strip())
    host = s.hostname or ""
    netloc = host.lower()
    if s.port:
        netloc += f":{s.port}"
    query = urlencode([(k, v) for k, v in parse_qsl(s.query) if not _TRACKING.match(k)])
    path = s.path.rstrip("/") or "/"
    return urlunsplit((s.scheme.lower(), netloc, path, query, ""))


def content_hash(text: str) -> str:
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()


def source_id_for_url(url: str) -> str:
    return "url:" + hashlib.sha256(canonical_url(url).encode("utf-8")).hexdigest()[:32]


def source_id_for_path(path: str) -> str:
    return "file:" + hashlib.sha256(path.encode("utf-8")).hexdigest()[:32]


def source_id_for_text(text: str) -> str:
    return "text:" + content_hash(text)[:32]


def point_id(source_id: str, chunk_index: int) -> str:
    return str(uuid.uuid5(_NAMESPACE, f"{source_id}:{chunk_index}"))


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()
