"""Files adapter: read a local file (or walk configured roots) and extract text.
PDFs go through pypdf; everything else is read as text."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Iterator

from ..core.document import Document, RawItem
from ..core.ids import content_hash, source_id_for_path
from .base import SourceAdapter
from .registry import register

_TEXT_SUFFIXES = {".md", ".txt", ".rst", ".csv", ".json", ".yaml", ".yml", ".py", ".log"}


@register
class FileAdapter(SourceAdapter):
    capability = "files"

    @property
    def supports_incremental(self) -> bool:
        return True

    def capture(self, *, path: str, tags: tuple[str, ...] = (), user_id: str = "owner",
                **_: Any) -> Document | None:
        p = Path(path).expanduser()
        if not p.is_file():
            raise FileNotFoundError(path)
        return self.normalize(RawItem(source_id=source_id_for_path(str(p.resolve())),
                                      payload={"path": str(p.resolve())},
                                      meta={"tags": tags, "user_id": user_id}))

    def discover(self, since: str | None) -> Iterator[RawItem]:
        for root in self.settings.get("roots", []):
            base = Path(root).expanduser()
            for p in base.rglob("*"):
                if p.is_file() and _supported(p):
                    yield RawItem(source_id=source_id_for_path(str(p.resolve())),
                                  payload={"path": str(p.resolve())},
                                  etag=f"{p.stat().st_mtime_ns}:{p.stat().st_size}")

    def normalize(self, item: RawItem) -> Document | None:
        p = Path(item.payload["path"])
        text = _extract(p)
        if not text.strip():
            return None
        meta = item.meta or {}
        return Document(
            source_id=item.source_id, capability=self.capability, title=p.name, text=text,
            content_hash=content_hash(text), uri=str(p),
            tags=tuple(meta.get("tags", ())), user_id=meta.get("user_id", "owner"),
            incremental_token=item.etag, meta={"ext": p.suffix.lstrip(".")},
        )


def _supported(p: Path) -> bool:
    return p.suffix.lower() in _TEXT_SUFFIXES or p.suffix.lower() == ".pdf"


def _extract(p: Path) -> str:
    if p.suffix.lower() == ".pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(p))
        return "\n\n".join((page.extract_text() or "") for page in reader.pages)
    return p.read_text(errors="replace")
