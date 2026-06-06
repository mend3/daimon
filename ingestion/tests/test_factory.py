import pytest

from ella_kb.core.config import Capability, EllaKbConfig
from ella_kb.adapters.base import AdapterContext
from ella_kb.adapters.registry import REGISTRY, build_enabled_adapters
from ella_kb.core.security import SSRFGuard
import ella_kb.adapters  # noqa: F401  (registers built-ins)
import httpx


def _ctx():
    return AdapterContext(ssrf=SSRFGuard(), http=httpx.Client())


def test_builtins_registered():
    assert {"files", "urls", "chat"} <= set(REGISTRY)


def test_factory_only_builds_enabled():
    cfg = EllaKbConfig(capabilities={"files": Capability(enabled=True),
                                     "urls": Capability(enabled=False)})
    built = build_enabled_adapters(cfg, _ctx())
    assert set(built) == {"files"}


def test_enabled_without_adapter_fails_closed():
    cfg = EllaKbConfig(capabilities={"nonexistent": Capability(enabled=True)})
    with pytest.raises(ValueError):
        build_enabled_adapters(cfg, _ctx())
