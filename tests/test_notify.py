from __future__ import annotations

import httpx
import pytest

from teilauto.api.errors import ConfigError
from teilauto.core.config import Settings
from teilauto.services.notify import (
    NtfyNotifier,
    TelegramNotifier,
    build_notifiers,
    send_all,
)


def _settings(**kw) -> Settings:
    base = dict(
        lat=51.0, lng=12.0, radius_m=500, min_fuel=0.0, window_min=30, interval_sec=120,
        prov_id="118", channels=(), tg_chat_id="", ntfy_topic="", ntfy_server="https://ntfy.sh",
    )
    base.update(kw)
    return Settings(**base)


def test_telegram_sends(respx_mock):
    route = respx_mock.post("https://api.telegram.org/botTOK/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    TelegramNotifier("TOK", "42").send("Title", "Body")
    body = route.calls.last.request.content.decode()
    assert "chat_id=42" in body
    assert "Title" in body


def test_ntfy_sends_title_header(respx_mock):
    route = respx_mock.post("https://ntfy.sh/my-topic").mock(return_value=httpx.Response(200))
    NtfyNotifier("https://ntfy.sh", "my-topic").send("Car booked", "VW Polo")
    req = route.calls.last.request
    assert req.headers["title"] == "Car booked"
    assert req.content == b"VW Polo"


def test_build_notifiers_from_settings(monkeypatch):
    monkeypatch.setenv("TEILAUTO_TG_BOT_TOKEN", "TOK")
    notifiers = build_notifiers(
        _settings(channels=("telegram", "ntfy"), tg_chat_id="42", ntfy_topic="t")
    )
    assert [n.name for n in notifiers] == ["telegram", "ntfy"]


def test_build_notifiers_missing_telegram_config(monkeypatch):
    monkeypatch.delenv("TEILAUTO_TG_BOT_TOKEN", raising=False)
    monkeypatch.setattr(
        "teilauto.services.notify.base.load_secret", lambda name: None
    )
    with pytest.raises(ConfigError, match="[Tt]elegram"):
        build_notifiers(_settings(channels=("telegram",), tg_chat_id="42"))


def test_build_notifiers_unknown_channel():
    with pytest.raises(ConfigError, match="pigeon"):
        build_notifiers(_settings(channels=("pigeon",)))


def test_send_all_isolates_failures(respx_mock):
    respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(500))
    errors = send_all([NtfyNotifier("https://ntfy.sh", "t")], "x", "y")
    assert len(errors) == 1
    assert "ntfy" in errors[0]


def test_send_all_never_leaks_telegram_token(respx_mock):
    respx_mock.post("https://api.telegram.org/botSECRET123/sendMessage").mock(
        return_value=httpx.Response(400, json={"ok": False})
    )
    errors = send_all([TelegramNotifier("SECRET123", "42")], "t", "m")
    assert len(errors) == 1
    assert "SECRET123" not in errors[0]
    assert "400" in errors[0]
