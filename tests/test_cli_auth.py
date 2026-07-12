from __future__ import annotations

import json

import httpx

from teilauto.cli import cli
from teilauto.core import tokenstore


def test_login_stores_token(runner, isolated_config, respx_mock, token_json):
    respx_mock.post("https://de1.cantamen.de/casirest/v3/tokens").mock(
        return_value=httpx.Response(200, json=token_json)
    )
    result = runner.invoke(cli, ["auth", "login"], input="me@example.org\nhunter2\n")
    assert result.exit_code == 0, result.output
    assert "Logged in" in result.output
    stored = tokenstore.load_token()
    assert stored is not None and stored.id == "tok-abc123"


def test_status_logged_in_json(runner, logged_in):
    result = runner.invoke(cli, ["auth", "status", "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["logged_in"] is True
    assert data["customer_id"] == "cust-9"


def test_status_not_logged_in_exits_3(runner, isolated_config):
    result = runner.invoke(cli, ["auth", "status"])
    assert result.exit_code == 3
    assert "Not logged in" in result.output


def test_logout_removes_token(runner, logged_in):
    result = runner.invoke(cli, ["auth", "logout"])
    assert result.exit_code == 0
    assert tokenstore.load_token() is None
