from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import keyring

from teilauto.core.config import config_dir

SERVICE = "teilauto-cli"
TOKEN_KEY = "cantamen-token"
TG_BOT_TOKEN_KEY = "telegram-bot-token"

_warned_fallback = False


@dataclass(frozen=True)
class StoredToken:
    id: str
    expiry: str | None
    customer_id: str | None


def _secrets_file() -> Path:
    return config_dir() / "secrets.json"


def _warn_fallback() -> None:
    global _warned_fallback
    if not _warned_fallback:
        print(
            "warning: no usable OS keyring; storing secrets in "
            f"{_secrets_file()} (chmod 600)",
            file=sys.stderr,
        )
        _warned_fallback = True


def _file_read() -> dict:
    path = _secrets_file()
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _file_write(data: dict) -> None:
    path = _secrets_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    path.chmod(0o600)


def save_secret(name: str, value: str) -> None:
    try:
        keyring.set_password(SERVICE, name, value)
    except Exception:
        _warn_fallback()
        data = _file_read()
        data[name] = value
        _file_write(data)


def load_secret(name: str) -> str | None:
    try:
        value = keyring.get_password(SERVICE, name)
    except Exception:
        value = None
    if value is not None:
        return value
    return _file_read().get(name)


def delete_secret(name: str) -> None:
    try:
        keyring.delete_password(SERVICE, name)
    except Exception:
        pass
    data = _file_read()
    if name in data:
        del data[name]
        _file_write(data)


def save_token(token: StoredToken) -> None:
    save_secret(
        TOKEN_KEY,
        json.dumps({"id": token.id, "expiry": token.expiry, "customer_id": token.customer_id}),
    )


def load_token() -> StoredToken | None:
    env_token = os.getenv("TEILAUTO_TOKEN")
    if env_token:
        return StoredToken(id=env_token, expiry=None, customer_id=None)
    raw = load_secret(TOKEN_KEY)
    if not raw:
        return None
    data = json.loads(raw)
    return StoredToken(
        id=data["id"], expiry=data.get("expiry"), customer_id=data.get("customer_id")
    )


def delete_token() -> None:
    delete_secret(TOKEN_KEY)
