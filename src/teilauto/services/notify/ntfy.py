from __future__ import annotations

import httpx


class NtfyNotifier:
    name = "ntfy"

    def __init__(self, server: str, topic: str) -> None:
        self._url = f"{server.rstrip('/')}/{topic}"

    def send(self, title: str, message: str) -> None:
        # HTTP headers are latin-1: keep titles ASCII, emoji go in the body.
        headers = {"Title": title} if title else {}
        resp = httpx.post(self._url, content=message.encode(), headers=headers, timeout=20.0)
        resp.raise_for_status()
