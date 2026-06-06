"""Node registry + factory. @node registers a handler by its NodeType.type; the
catalog (the palette) is derived from what's registered."""
from __future__ import annotations

import importlib.metadata as md

from .spec import NodeHandler, NodeType

REGISTRY: dict[str, type[NodeHandler]] = {}


def node(cls: type[NodeHandler]) -> type[NodeHandler]:
    t = cls.node_type.type
    if t in REGISTRY and REGISTRY[t] is not cls:
        raise ValueError(f"duplicate node type {t!r}")
    REGISTRY[t] = cls
    return cls


def load_external_nodes() -> None:
    try:
        eps = md.entry_points(group="ella_flow.nodes")
    except TypeError:
        eps = md.entry_points().get("ella_flow.nodes", [])  # type: ignore[attr-defined]
    for ep in eps:
        ep.load()


_loaded = False


def ensure_loaded() -> None:
    """Import built-in + external node modules once so REGISTRY is populated."""
    global _loaded
    if _loaded:
        return
    import ella_flow.nodes  # noqa: F401  (built-in registration via @node)
    load_external_nodes()
    _loaded = True


def make_handler(node_type: str) -> NodeHandler:
    ensure_loaded()
    if node_type not in REGISTRY:
        raise ValueError(f"unknown node type {node_type!r}")
    return REGISTRY[node_type]()


def catalog() -> list[NodeType]:
    ensure_loaded()
    return [cls.node_type for cls in REGISTRY.values()]
