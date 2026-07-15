"""Minimal Ollama chat client for agent nodes (and the web chat). Uses the native
/api/chat endpoint; reads Daimon's system prompt from ~/.hermes/SOUL.md when present."""
from __future__ import annotations

import os
from pathlib import Path

import httpx

_SOUL = Path("~/.hermes/SOUL.md").expanduser()


def soul_prompt() -> str:
    return _SOUL.read_text() if _SOUL.exists() else "You are Daimon, a warm, capable companion."


class OllamaChat:
    def __init__(self, base_url: str | None = None, model: str = "gpt-oss:20b", timeout: float = 600):
        self.base_url = (base_url or os.environ.get("OLLAMA_URL", "http://ollama:11434")).rstrip("/")
        self.model = model
        self._client = httpx.Client(timeout=timeout)

    def complete(self, prompt: str, system: str | None = None, model: str | None = None) -> str:
        messages = [{"role": "system", "content": system or soul_prompt()},
                    {"role": "user", "content": prompt}]
        r = self._client.post(f"{self.base_url}/api/chat",
                              json={"model": model or self.model, "messages": messages, "stream": False})
        r.raise_for_status()
        return r.json()["message"]["content"]

    def close(self) -> None:
        self._client.close()
