"""Inbound webhook receiver for the `webhook` source type. A minimal HTTP endpoint
(stdlib only) that authenticates each POST with an HMAC-SHA256 signature, then
ingests the JSON body. Bind to loopback; put it behind the host firewall.

POST /ingest  body: {"text": "...", "title"?, "url"?, "tags"?, "source_app"?}
header: X-Signature: sha256=<hmac of the raw body using KB_WEBHOOK_SECRET>"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..service import KnowledgeBase

_kb: KnowledgeBase | None = None
_secret = b""


def _valid(sig_header: str | None, body: bytes) -> bool:
    if not _secret or not sig_header:
        return False
    expected = "sha256=" + hmac.new(_secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, sig_header)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/ingest":
            return self._send(404, {"error": "not found"})
        body = self.rfile.read(int(self.headers.get("content-length", 0)))
        if not _valid(self.headers.get("x-signature"), body):
            return self._send(401, {"error": "bad signature"})
        try:
            payload = json.loads(body)
            res = _kb.ingest_push("webhook", payload)  # type: ignore[union-attr]
        except Exception as e:  # noqa: BLE001
            return self._send(400, {"error": str(e)})
        if res is None:
            return self._send(422, {"error": "no usable content"})
        self._send(200, {"status": "deduped" if res.deduped else "indexed", "title": res.title})

    def _send(self, code: int, obj: dict) -> None:
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_: object) -> None:
        pass  # quiet


def main() -> None:
    global _kb, _secret
    _secret = os.environ.get("KB_WEBHOOK_SECRET", "").encode()
    if not _secret:
        raise SystemExit("KB_WEBHOOK_SECRET is not set")
    _kb = KnowledgeBase()
    _kb.ensure_collections()
    host, _, port = os.environ.get("KB_WEBHOOK_BIND", "127.0.0.1:8771").rpartition(":")
    server = ThreadingHTTPServer((host or "127.0.0.1", int(port)), _Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
