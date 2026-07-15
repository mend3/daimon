import pytest

from daimon_kb.core.config import Capability, DaimonKbConfig
from daimon_kb.adapters.base import AdapterContext
from daimon_kb.adapters.registry import REGISTRY, build_enabled_adapters
from daimon_kb.core.security import SSRFGuard
import daimon_kb.adapters  # noqa: F401  (registers built-ins)
import httpx


def _ctx():
    return AdapterContext(ssrf=SSRFGuard(), http=httpx.Client())


def test_builtins_registered():
    assert {"files", "urls", "chat"} <= set(REGISTRY)


def test_factory_only_builds_enabled():
    cfg = DaimonKbConfig(capabilities={"files": Capability(enabled=True),
                                     "urls": Capability(enabled=False)})
    built = build_enabled_adapters(cfg, _ctx())
    assert set(built) == {"files"}


def test_enabled_without_adapter_fails_closed():
    cfg = DaimonKbConfig(capabilities={"nonexistent": Capability(enabled=True)})
    with pytest.raises(ValueError):
        build_enabled_adapters(cfg, _ctx())
