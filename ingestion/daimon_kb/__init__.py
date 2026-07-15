"""Daimon's personal RAG knowledge base.

A source-agnostic ingestion + retrieval pipeline. Sources plug in as adapters
(Adapter + Factory patterns); each enabled source type is a capability backed by
its own Qdrant collection. The deterministic core never lets the language model
touch chunking, embedding, or vector math.
"""

__version__ = "0.1.0"
