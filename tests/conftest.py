from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import CliRunner

from teilauto.core import tokenstore as _tokenstore
from teilauto.core.tokenstore import StoredToken

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def poi_json():
    return load_fixture("pointsofinterest.json")


@pytest.fixture
def proposals_json():
    return load_fixture("bookingproposals.json")


@pytest.fixture
def prices_json():
    return load_fixture("prices.json")


@pytest.fixture
def bookings_json():
    return load_fixture("bookings.json")


@pytest.fixture
def token_json():
    return load_fixture("token.json")


@pytest.fixture
def unavailabilities_json():
    return load_fixture("unavailabilities.json")


class _NoKeyring:
    def set_password(self, *a):
        raise RuntimeError("no keyring in tests")

    def get_password(self, *a):
        raise RuntimeError("no keyring in tests")

    def delete_password(self, *a):
        raise RuntimeError("no keyring in tests")


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    monkeypatch.setenv("TEILAUTO_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("TEILAUTO_TOKEN", raising=False)
    monkeypatch.delenv("TEILAUTO_TG_BOT_TOKEN", raising=False)
    monkeypatch.setattr(_tokenstore, "keyring", _NoKeyring())
    return tmp_path


@pytest.fixture
def logged_in(isolated_config):
    _tokenstore.save_token(
        StoredToken(id="tok-abc123", expiry="2026-10-10T00:00:00.000Z", customer_id="cust-9")
    )
    return isolated_config
