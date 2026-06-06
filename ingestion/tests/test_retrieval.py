"""Recall ranking (merge_hits): a document contributes up to max_per_source chunks,
exact duplicate chunks are dropped, and near-duplicates from other sources are too."""
from ella_kb.core.store import SearchHit
from ella_kb.service import merge_hits


def _hit(sid, ci, score, ch):
    return SearchHit(score=score, source_id=sid, source_type="files", title="t",
                     text=f"{sid}-{ci}", uri=None, chunk_index=ci, payload={"content_hash": ch})


def test_keeps_multiple_chunks_per_source_up_to_cap():
    hits = [_hit("s1", i, 0.9 - i * 0.1, "h1") for i in range(4)]
    out = merge_hits(hits, final_k=8, max_per_source=3)
    assert len(out) == 3   # capped at max_per_source, not collapsed to one


def test_drops_exact_and_cross_source_duplicates():
    hits = [_hit("s1", 0, 0.9, "hX"), _hit("s2", 0, 0.85, "hX"), _hit("s1", 0, 0.8, "hX")]
    out = merge_hits(hits, final_k=8, max_per_source=3)
    assert len(out) == 1   # s2 duplicates hX from another source; s1:0 repeats exactly
