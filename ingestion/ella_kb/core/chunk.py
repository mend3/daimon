"""Deterministic, boundary-aware chunking. Splits on paragraph, then sentence,
then hard-wrap, so chunks don't cut mid-thought. Char-based (dependency-light);
sizes are tuned for the small retrieval budget of a local model."""
from __future__ import annotations

import re

_PARA = re.compile(r"\n\s*\n")
_SENT = re.compile(r"(?<=[.!?])\s+")


def chunk_text(text: str, target_chars: int = 1100, overlap_chars: int = 150) -> list[str]:
    text = text.strip()
    if not text:
        return []
    if len(text) <= target_chars:
        return [text]

    units = _split_units(text, target_chars)
    chunks: list[str] = []
    buf = ""
    for unit in units:
        if buf and len(buf) + 1 + len(unit) > target_chars:
            chunks.append(buf)
            buf = (buf[-overlap_chars:] + " " + unit) if overlap_chars else unit
        else:
            buf = f"{buf} {unit}".strip() if buf else unit
    if buf:
        chunks.append(buf)
    return chunks


def _split_units(text: str, target_chars: int) -> list[str]:
    units: list[str] = []
    for para in _PARA.split(text):
        para = para.strip()
        if not para:
            continue
        if len(para) <= target_chars:
            units.append(para)
            continue
        for sent in _SENT.split(para):
            sent = sent.strip()
            if not sent:
                continue
            if len(sent) <= target_chars:
                units.append(sent)
            else:
                units.extend(_hard_wrap(sent, target_chars))
    return units


def _hard_wrap(s: str, size: int) -> list[str]:
    return [s[i : i + size] for i in range(0, len(s), size)]
