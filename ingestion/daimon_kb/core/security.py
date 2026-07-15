"""Security boundaries applied before content is fetched or embedded.

SSRFGuard keeps adapters that fetch user-supplied URLs from reaching the host's
private network or cloud metadata. SecretRedactor scrubs obvious secrets so they
never land in the vector store (the worker is a separate process from chat-time
redaction, so it re-checks)."""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit


class SSRFError(ValueError):
    pass


_ALLOWED_SCHEMES = {"http", "https"}


class SSRFGuard:
    def __init__(self, allow_private: bool = False, allowed_schemes: set[str] | None = None):
        self.allow_private = allow_private
        self.allowed_schemes = allowed_schemes or set(_ALLOWED_SCHEMES)

    def check(self, url: str) -> None:
        """Raise SSRFError if the URL must not be fetched. Call again after every
        redirect, since the final hop is what matters."""
        s = urlsplit(url)
        if s.scheme.lower() not in self.allowed_schemes:
            raise SSRFError(f"scheme not allowed: {s.scheme!r}")
        host = s.hostname
        if not host:
            raise SSRFError("missing host")
        if self.allow_private:
            return
        for family, _, _, _, sockaddr in socket.getaddrinfo(host, None):
            ip = ipaddress.ip_address(sockaddr[0])
            if (
                ip.is_private
                or ip.is_loopback
                or ip.is_link_local
                or ip.is_reserved
                or ip.is_multicast
                or ip.is_unspecified
            ):
                raise SSRFError(f"blocked address for {host}: {ip}")


_SECRET_PATTERNS = [
    re.compile(r"\b(sk|pk|rk)-[A-Za-z0-9]{16,}\b"),                 # API keys
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                            # AWS access key
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),                  # GitHub tokens
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),               # Slack tokens
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----"),
]
_REDACTED = "[REDACTED]"


class SecretRedactor:
    def redact(self, text: str) -> str:
        for pat in _SECRET_PATTERNS:
            text = pat.sub(_REDACTED, text)
        return text
