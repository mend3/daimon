"""End-to-end against a live Qdrant + Ollama. Skipped unless ELLA_KB_IT=1 and the
services are reachable (set QDRANT_URL/QDRANT_API_KEY/embeddings via env or config)."""
import os
import uuid

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("ELLA_KB_IT") != "1",
                                reason="integration test (set ELLA_KB_IT=1)")


@pytest.fixture
def kb():
    from ella_kb.core.config import Capability, EllaKbConfig, EmbedCfg, QdrantCfg
    from ella_kb.service import KnowledgeBase

    tag = "it" + uuid.uuid4().hex[:8]  # isolate collections per run
    cfg = EllaKbConfig(
        ledger_path=f"/tmp/ella_kb_{tag}.db",
        qdrant=QdrantCfg(url=os.environ["QDRANT_URL"], api_key=os.environ.get("QDRANT_API_KEY")),
        embeddings=EmbedCfg(base_url=os.environ.get("OLLAMA_URL", "http://localhost:11434"), tag=tag),
        capabilities={"chat": Capability(enabled=True), "files": Capability(enabled=True),
                      "urls": Capability(enabled=True)},
    )
    kb = KnowledgeBase(cfg)
    kb.ensure_collections()
    return kb


def test_capture_note_and_recall(kb):
    kb.capture(text="The deployment runbook lives in the ops wiki under 'release checklist'.",
               title="runbook location")
    kb.capture(text="Our payment provider is Stripe; webhooks hit /api/payments/hook.")
    hits = kb.recall("where do I find the release steps?")
    assert hits, "expected a relevant hit"
    assert "runbook" in (hits[0].title + hits[0].text).lower()


def test_recall_scope(kb):
    kb.capture(text="A note about coffee brewing ratios: 1:16 water to coffee.")
    assert kb.recall("coffee ratio", scope=["chat"])
    assert kb.recall("coffee ratio", scope=["files"]) == []


def test_dedup_on_recapture(kb):
    r1 = kb.capture(text="Idempotency check: this exact note should dedupe on re-save.")
    r2 = kb.capture(text="Idempotency check: this exact note should dedupe on re-save.")
    assert not r1.deduped and r2.deduped


def test_forget(kb):
    kb.capture(text="Ephemeral fact to be forgotten shortly.", title="ephemeral")
    assert kb.forget("ephemeral")
    assert not kb.recall("ephemeral fact", scope=["chat"])
