# ella_kb — Ella's knowledge base

A source-agnostic RAG pipeline. The deterministic `core/` (chunk, embed, store,
ledger, security) never lets the language model touch vectors. Sources plug in as
**adapters**; each enabled source type is a capability backed by its own Qdrant
collection (`kb_<type>__nomic768`).

## Layout

- `core/` — `document`, `ids`, `chunk`, `embed`, `store`, `ledger`, `security`,
  `pipeline`, `config`. Imports nothing from `adapters/`.
- `adapters/` — `base` (the contract), `registry`/`factory`, and one module per
  source type (`files`, `urls`, `chat`, `feeds`, `webhook`).
- `service.py` — `KnowledgeBase`, the facade (capture / recall / forget / poll).
- `apps/` — `mcp_server` (tools for Ella), `webhook_receiver`.
- `cli.py` — `ella-kb` (init, capture, recall, forget, recent, poll, webhook-serve).

## Adding a source type (zero core changes)

In-tree: add `adapters/<name>.py` with

```python
@register
class MyAdapter(SourceAdapter):
    capability = "myname"          # == enabled key == collection suffix
    def normalize(self, item): ... # RawItem -> Document (or None to skip)
    # optional: discover(since) for polling, capture(**kw) for /save,
    #           after_ingest(items) to acknowledge a batch
```

then import it in `adapters/__init__.py` and enable it in `config/ella_kb.yaml`.

Out-of-tree: ship a package exposing an `ella_kb.adapters` entry point; `pip install`
it into the Hermes venv and enable it in config. The factory builds only enabled
capabilities and fails closed if one has no adapter.

The pipeline (dedup → redact → chunk → embed → upsert → ledger) is shared and
deterministic; an adapter only decides *what* to ingest and *where from*.

## Tests

`pip install -e .[dev]` then `pytest`. Integration tests need a live Qdrant +
Ollama and `ELLA_KB_IT=1` (see `tests/test_integration.py`).
