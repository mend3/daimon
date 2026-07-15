"""Registry + Factory. @register records an adapter class under its capability;
build_enabled_adapters instantiates only the capabilities enabled in config and
fails closed if an enabled capability has no adapter."""
from __future__ import annotations

import importlib.metadata as md

from ..core.config import DaimonKbConfig
from .base import AdapterContext, SourceAdapter

REGISTRY: dict[str, type[SourceAdapter]] = {}


def register(cls: type[SourceAdapter]) -> type[SourceAdapter]:
    name = cls.capability
    if not name:
        raise ValueError(f"{cls.__name__} must set a non-empty `capability`")
    if name in REGISTRY and REGISTRY[name] is not cls:
        raise ValueError(f"duplicate capability {name!r}")
    REGISTRY[name] = cls
    return cls


def load_external_adapters() -> None:
    """Discover out-of-tree adapters declared via the `daimon_kb.adapters` entry point."""
    try:
        eps = md.entry_points(group="daimon_kb.adapters")
    except TypeError:  # older importlib API
        eps = md.entry_points().get("daimon_kb.adapters", [])  # type: ignore[attr-defined]
    for ep in eps:
        ep.load()  # importing the target fires its @register


def build_enabled_adapters(cfg: DaimonKbConfig, ctx: AdapterContext) -> dict[str, SourceAdapter]:
    load_external_adapters()
    enabled: dict[str, SourceAdapter] = {}
    for name in cfg.enabled_capabilities():
        if name not in REGISTRY:
            raise ValueError(f"capability {name!r} is enabled but no adapter is registered")
        enabled[name] = REGISTRY[name](cfg.capabilities[name].settings, ctx)
    return enabled
