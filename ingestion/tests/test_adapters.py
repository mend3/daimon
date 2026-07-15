import hashlib
import hmac

import httpx

import pytest

from daimon_kb.adapters.base import AdapterContext
from daimon_kb.adapters.feeds import FeedAdapter, _passes_triage, _strip_html
from daimon_kb.adapters.urls import UrlAdapter
from daimon_kb.adapters.webhook import WebhookAdapter
from daimon_kb.core.document import RawItem
from daimon_kb.core.security import SSRFError, SSRFGuard


def _ctx():
    return AdapterContext(ssrf=SSRFGuard(), http=httpx.Client())


def test_strip_html():
    assert _strip_html("<p>Hello <b>world</b></p><script>x()</script>") == "Hello world"


def test_feeds_triage_include_exclude():
    assert _passes_triage("A post about Rust and WASM", {"include": ["rust"]})
    assert not _passes_triage("A post about cooking", {"include": ["rust"]})
    assert not _passes_triage("Crypto pump signals", {"exclude": ["crypto"]})
    assert _passes_triage("anything", {})  # no filters = keep


def test_feeds_normalize_skips_filtered():
    a = FeedAdapter({"include": ["python"]}, _ctx())
    entry = {"id": 1, "url": "https://x.io/a", "title": "About Go",
             "content": "<p>" + "go lang " * 40 + "</p>", "feed": {"title": "X"}}
    assert a.normalize(RawItem(source_id="url:1", payload=entry, meta={"entry_id": 1})) is None


def test_feeds_normalize_keeps_matching():
    a = FeedAdapter({"include": ["python"]}, _ctx())
    entry = {"id": 2, "url": "https://x.io/b", "title": "Python tips",
             "content": "<p>" + "python rocks " * 40 + "</p>", "feed": {"title": "X"}}
    doc = a.normalize(RawItem(source_id="url:2", payload=entry, meta={"entry_id": 2}))
    assert doc is not None and doc.capability == "feeds" and "python" in doc.text.lower()


class _StubGuard:
    def check(self, url):
        if "169.254" in url or "127.0.0.1" in url:
            raise SSRFError(url)


class _Resp:
    def __init__(self, status, location=None):
        self.status_code = status
        self.headers = {"location": location} if location else {}
        self.url = ""

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308)


class _Http:
    def __init__(self, responses):
        self.responses, self.calls = responses, []

    def get(self, url, timeout=None, follow_redirects=False):
        self.calls.append(url)
        r = self.responses.pop(0)
        r.url = url
        return r


def test_url_redirect_to_private_blocked_before_fetch():
    http = _Http([_Resp(302, location="http://169.254.169.254/latest")])
    adapter = UrlAdapter({}, AdapterContext(ssrf=_StubGuard(), http=http))
    with pytest.raises(SSRFError):
        adapter.fetch(RawItem(source_id="url:x", payload={"url": "http://public.example/"}))
    assert http.calls == ["http://public.example/"]  # the private hop was never fetched


def test_webhook_normalize_and_signature():
    a = WebhookAdapter({}, _ctx())
    doc = a.normalize(RawItem(source_id="push", payload={"text": "hello from app", "title": "t"}))
    assert doc and doc.capability == "webhook" and doc.title == "t"
    assert a.normalize(RawItem(source_id="push", payload={"text": "  "})) is None

    secret = b"s3cret"
    body = b'{"text":"x"}'
    sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    from daimon_kb.apps import webhook_receiver as wr
    wr._secret = secret
    assert wr._valid(sig, body)
    assert not wr._valid("sha256=deadbeef", body)
