from __future__ import annotations

import httpx


class TelegramNotifier:
    name = "telegram"

    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def send(self, title: str, message: str) -> None:
        text = f"{title}\n{message}" if title else message
        try:
            resp = httpx.post(
                f"https://api.telegram.org/bot{self._bot_token}/sendMessage",
                data={"chat_id": self._chat_id, "text": text},
                timeout=20.0,
            )
        except httpx.HTTPError as exc:  # transport errors; never expose exc text (may embed URL)
            raise RuntimeError(f"Telegram request failed ({type(exc).__name__})") from exc
        if resp.status_code >= 400:
            raise RuntimeError(f"Telegram API returned HTTP {resp.status_code}")
