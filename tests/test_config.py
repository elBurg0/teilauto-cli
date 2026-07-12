from __future__ import annotations

import pytest

from teilauto.core import config as cfg


@pytest.fixture
def config_home(tmp_path, monkeypatch):
    monkeypatch.setenv("TEILAUTO_CONFIG_DIR", str(tmp_path))
    return tmp_path


def test_defaults_when_no_file(config_home):
    s = cfg.load_settings()
    assert (s.lat, s.lng, s.radius_m) == (51.33853, 12.39163, 500)
    assert s.interval_sec == 120
    assert s.channels == ()
    assert s.ntfy_server == "https://ntfy.sh"


def test_file_overrides_defaults(config_home):
    data = cfg.read_raw()
    cfg.set_value(data, "location.radius_m", 900)
    cfg.set_value(data, "notify.channels", ["telegram"])
    cfg.set_value(data, "notify.telegram.chat_id", "42")
    cfg.write_raw(data)
    s = cfg.load_settings()
    assert s.radius_m == 900
    assert s.channels == ("telegram",)
    assert s.tg_chat_id == "42"


def test_env_overrides_file(config_home, monkeypatch):
    data = cfg.read_raw()
    cfg.set_value(data, "location.radius_m", 900)
    cfg.write_raw(data)
    monkeypatch.setenv("TEILAUTO_LOCATION_RADIUS_M", "250")
    monkeypatch.setenv("TEILAUTO_NOTIFY_CHANNELS", "telegram,ntfy")
    s = cfg.load_settings()
    assert s.radius_m == 250
    assert s.channels == ("telegram", "ntfy")


def test_channels_string_becomes_tuple(config_home):
    data = cfg.read_raw()
    cfg.set_value(data, "notify.channels", "telegram")
    cfg.write_raw(data)
    assert cfg.load_settings().channels == ("telegram",)


def test_get_set_unset_roundtrip(config_home):
    data = cfg.read_raw()
    cfg.set_value(data, "defaults.min_fuel", 25.0)
    assert cfg.get_value(data, "defaults.min_fuel") == 25.0
    cfg.unset_value(data, "defaults.min_fuel")
    assert cfg.get_value(data, "defaults.min_fuel") is None


def test_coerce_value():
    assert cfg.coerce_value("true") is True
    assert cfg.coerce_value("42") == 42
    assert cfg.coerce_value("1.5") == 1.5
    assert cfg.coerce_value("a,b") == ["a", "b"]
    assert cfg.coerce_value("hello") == "hello"


def test_effective_config_is_flat(config_home):
    flat = cfg.effective_config()
    assert flat["location.lat"] == 51.33853
    assert "notify.ntfy.server" in flat
    assert set(flat) == set(cfg.KNOWN_KEYS)


def test_config_file_under_config_dir(config_home):
    assert cfg.config_file().parent == config_home
