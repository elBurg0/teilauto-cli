from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Protocol

from teilauto.api.errors import ConfigError
from teilauto.core.config import Settings
from teilauto.core.tokenstore import TG_BOT_TOKEN_KEY, load_secret
from teilauto.services.notify.ntfy import NtfyNotifier
from teilauto.services.notify.telegram import TelegramNotifier


class Notifier(Protocol):
    name: str

    def send(self, title: str, message: str) -> None: ...


def build_notifiers(settings: Settings) -> list[Notifier]:
    notifiers: list[Notifier] = []
    for channel in settings.channels:
        if channel == "telegram":
            token = os.getenv("TEILAUTO_TG_BOT_TOKEN") or load_secret(TG_BOT_TOKEN_KEY)
            if not token or not settings.tg_chat_id:
                raise ConfigError(
                    "Telegram channel is configured but bot token or chat_id is missing.",
                    hint=(
                        "Set the token with `teilauto config set notify.telegram.bot_token "
                        "<token>` and the chat with `teilauto config set "
                        "notify.telegram.chat_id <id>`."
                    ),
                )
            notifiers.append(TelegramNotifier(token, settings.tg_chat_id))
        elif channel == "ntfy":
            if not settings.ntfy_topic:
                raise ConfigError(
                    "ntfy channel is configured but no topic is set.",
                    hint="Run `teilauto config set notify.ntfy.topic <topic>`.",
                )
            notifiers.append(NtfyNotifier(settings.ntfy_server, settings.ntfy_topic))
        else:
            raise ConfigError(
                f"Unknown notification channel: {channel!r}.",
                hint="Valid channels: telegram, ntfy.",
            )
    return notifiers


def send_all(notifiers: Sequence[Notifier], title: str, message: str) -> list[str]:
    """Send to every notifier; never raises. Returns human-readable error strings."""
    errors: list[str] = []
    for notifier in notifiers:
        try:
            notifier.send(title, message)
        except Exception as exc:
            errors.append(f"{notifier.name}: {exc}")
    return errors
