from __future__ import annotations

import click
import pytest

from teilauto.cli import cli, main
from teilauto.cli.options import resolve_location, resolve_window
from teilauto.core.config import Settings
from teilauto.output.render import fuel_text, local_time

SETTINGS = Settings(
    lat=51.0,
    lng=12.0,
    radius_m=500,
    min_fuel=0.0,
    window_min=30,
    interval_sec=120,
    prov_id="118",
    channels=(),
    tg_chat_id="",
    ntfy_topic="",
    ntfy_server="https://ntfy.sh",
)


def test_help_lists_groups(runner, isolated_config):
    result = runner.invoke(cli, ["-h"])
    assert result.exit_code == 0


def test_resolve_location_flag_beats_settings():
    assert resolve_location(SETTINGS, 50.0, None, None) == (50.0, 12.0, 500)
    assert resolve_location(SETTINGS, None, None, 900) == (51.0, 12.0, 900)


def test_resolve_window_default_minutes():
    start, end = resolve_window("now", None, None, default_minutes=30)
    assert (end - start).total_seconds() == 30 * 60


def test_resolve_window_for_and_until_conflict():
    with pytest.raises(click.UsageError, match="mutually exclusive"):
        resolve_window("now", "1h", "18:00", default_minutes=30)


def test_resolve_window_bad_time_is_bad_parameter():
    with pytest.raises(click.BadParameter, match="Cannot parse"):
        resolve_window("banana", None, None, default_minutes=30)


def test_main_renders_teilauto_error(monkeypatch, capsys, isolated_config):
    monkeypatch.setattr("sys.argv", ["teilauto", "bookings", "list"])
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 3  # not logged in
    err = capsys.readouterr().err
    assert "auth login" in err


def test_fuel_text_colors():
    assert fuel_text(80).style == "green"
    assert fuel_text(30).style == "yellow"
    assert fuel_text(10).style == "red"
    assert "?" in str(fuel_text(None))


def test_local_time_handles_z_and_none():
    assert local_time(None) == "—"
    assert local_time("2026-07-12T10:00:00.000Z") != "—"


def _register_hidden(name, fn):
    cmd = click.command(name=name, hidden=True)(fn)
    cli.add_command(cmd)
    return cmd


def test_main_propagates_nonzero_ctx_exit(monkeypatch, isolated_config):
    @click.pass_context
    def _exit7(ctx):
        ctx.exit(7)

    _register_hidden("_exit7", _exit7)
    try:
        monkeypatch.setattr("sys.argv", ["teilauto", "_exit7"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 7
    finally:
        cli.commands.pop("_exit7", None)


def test_main_ctrl_c_exits_130(monkeypatch, capsys, isolated_config):
    def _boom():
        raise KeyboardInterrupt

    _register_hidden("_boom", _boom)
    try:
        monkeypatch.setattr("sys.argv", ["teilauto", "_boom"])
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 130
        assert "Stopped" in capsys.readouterr().err
    finally:
        cli.commands.pop("_boom", None)


def test_local_time_unparseable_returns_dash():
    assert local_time("not-a-date") == "—"
