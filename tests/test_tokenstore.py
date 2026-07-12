from __future__ import annotations

import json
import stat
import sys

import pytest

from teilauto.core import tokenstore
from teilauto.core.tokenstore import StoredToken


class _WorkingKeyring:
    def __init__(self):
        self.store = {}

    def set_password(self, service, name, value):
        self.store[(service, name)] = value

    def get_password(self, service, name):
        return self.store.get((service, name))

    def delete_password(self, service, name):
        self.store.pop((service, name), None)


class _BrokenKeyring:
    def set_password(self, *a):
        raise RuntimeError("no backend")

    def get_password(self, *a):
        raise RuntimeError("no backend")

    def delete_password(self, *a):
        raise RuntimeError("no backend")


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TEILAUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("TEILAUTO_TOKEN", raising=False)
    return tmp_path


def test_secret_roundtrip_via_keyring(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _WorkingKeyring())
    tokenstore.save_secret("x", "s3cret")
    assert tokenstore.load_secret("x") == "s3cret"
    tokenstore.delete_secret("x")
    assert tokenstore.load_secret("x") is None


def test_file_fallback_when_keyring_broken(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    tokenstore.save_secret("x", "s3cret")
    secrets_file = config_home / "secrets.json"
    assert secrets_file.is_file()
    assert json.loads(secrets_file.read_text())["x"] == "s3cret"
    if sys.platform != "win32":
        assert stat.S_IMODE(secrets_file.stat().st_mode) == 0o600
    assert tokenstore.load_secret("x") == "s3cret"
    tokenstore.delete_secret("x")
    assert tokenstore.load_secret("x") is None


def test_token_roundtrip(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    token = StoredToken(id="tok-1", expiry="2026-10-10T00:00:00.000Z", customer_id="c1")
    tokenstore.save_token(token)
    assert tokenstore.load_token() == token
    tokenstore.delete_token()
    assert tokenstore.load_token() is None


def test_env_token_wins(config_home, monkeypatch):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    tokenstore.save_token(StoredToken(id="stored", expiry=None, customer_id=None))
    monkeypatch.setenv("TEILAUTO_TOKEN", "from-env")
    assert tokenstore.load_token() == StoredToken(id="from-env", expiry=None, customer_id=None)


def test_load_warns_once_when_fallback_file_exists(config_home, monkeypatch, capsys):
    monkeypatch.setattr(tokenstore, "keyring", _BrokenKeyring())
    tokenstore.save_secret("x", "s3cret")
    tokenstore._warned_fallback = False  # reset the one-time flag set by save
    assert tokenstore.load_secret("x") == "s3cret"
    tokenstore.load_secret("x")
    err = capsys.readouterr().err
    assert err.count("no usable OS keyring") == 1
