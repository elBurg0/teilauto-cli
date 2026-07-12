from __future__ import annotations

import json

import httpx

from teilauto.api.errors import ConfigError
from teilauto.cli import cli
from teilauto.core import config as cfg
from teilauto.core import tokenstore


def test_config_set_get_roundtrip(runner, isolated_config):
    assert runner.invoke(cli, ["config", "set", "location.radius_m", "900"]).exit_code == 0
    result = runner.invoke(cli, ["config", "get", "location.radius_m"])
    assert result.exit_code == 0
    assert result.output.strip() == "900"


def test_config_list_json_shows_effective(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "location.radius_m", "900"])
    result = runner.invoke(cli, ["config", "list", "--json"])
    data = json.loads(result.output)
    assert data["location.radius_m"] == 900
    assert data["location.lat"] == 51.3455  # default still present


def test_config_unknown_key_fails(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "nope.nope", "1"])
    assert result.exit_code != 0


def test_config_unset(runner, isolated_config):
    runner.invoke(cli, ["config", "set", "location.radius_m", "900"])
    assert runner.invoke(cli, ["config", "unset", "location.radius_m"]).exit_code == 0
    result = runner.invoke(cli, ["config", "get", "location.radius_m"])
    assert result.output.strip() == "500"  # back to default


def test_config_path(runner, isolated_config):
    result = runner.invoke(cli, ["config", "path"])
    assert result.exit_code == 0
    assert str(isolated_config) in result.output


def test_bot_token_goes_to_secret_store_not_toml(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "notify.telegram.bot_token", "TOK123"])
    assert result.exit_code == 0, result.output
    config_toml = isolated_config / "config.toml"
    assert "TOK123" not in (config_toml.read_text() if config_toml.exists() else "")
    assert tokenstore.load_secret(tokenstore.TG_BOT_TOKEN_KEY) == "TOK123"


def test_notify_test_no_channels(runner, isolated_config):
    result = runner.invoke(cli, ["notify", "test"])
    assert result.exit_code != 0


def test_notify_test_sends(runner, isolated_config, respx_mock, monkeypatch):
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "ntfy")
    monkeypatch.setenv("TEILAUTO_NOTIFY_NTFY_TOPIC", "t")
    route = respx_mock.post("https://ntfy.sh/t").mock(return_value=httpx.Response(200))
    result = runner.invoke(cli, ["notify", "test"])
    assert result.exit_code == 0, result.output
    assert route.called
    assert "ntfy" in result.output


def test_config_set_rejects_bad_type(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "location.lat", "abc"])
    assert result.exit_code != 0
    config_toml = isolated_config / "config.toml"
    if config_toml.exists():
        assert "lat" not in config_toml.read_text()


def test_config_unset_recovers_from_broken_value(runner, isolated_config):
    (isolated_config / "config.toml").write_text('[location]\nlat = "abc"\n')
    result = runner.invoke(cli, ["config", "unset", "location.lat"])
    assert result.exit_code == 0, result.output
    result = runner.invoke(cli, ["config", "get", "location.lat"])
    assert result.output.strip() == "51.3455"


def test_broken_config_surfaces_as_config_error_no_traceback(runner, isolated_config):
    (isolated_config / "config.toml").write_text('[location]\nlat = "abc"\n')
    result = runner.invoke(cli, ["cars", "list"])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Traceback" not in (result.stderr or "")
    assert isinstance(result.exception, ConfigError)


def test_config_set_numeric_string_converted_to_str_for_str_default(runner, isolated_config):
    result = runner.invoke(cli, ["config", "set", "notify.telegram.chat_id", "42"])
    assert result.exit_code == 0, result.output
    get_result = runner.invoke(cli, ["config", "get", "notify.telegram.chat_id"])
    assert get_result.output.strip() == "42"
    raw = cfg.read_raw(isolated_config / "config.toml")
    assert cfg.get_value(raw, "notify.telegram.chat_id") == "42"
    assert isinstance(cfg.get_value(raw, "notify.telegram.chat_id"), str)


def test_config_get_secret_key_shows_presence_not_value(runner, isolated_config):
    result = runner.invoke(cli, ["config", "get", "notify.telegram.bot_token"])
    assert result.exit_code == 0
    assert result.output.strip() == "(not set)"

    runner.invoke(cli, ["config", "set", "notify.telegram.bot_token", "TOK123"])
    result = runner.invoke(cli, ["config", "get", "notify.telegram.bot_token"])
    assert result.exit_code == 0
    assert result.output.strip() == "(set)"
    assert "TOK123" not in result.output
