from __future__ import annotations

import httpx


class TelegramNotifier:
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def send(self, title: str, message: str) -> None:
        text = f"{title}\n{message}" if title else message
        resp = httpx.post(
            f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
            data={"chat_id": self._chat_id, "text": text},
            timeout=20.0,
        )
        resp.raise_for_status()
