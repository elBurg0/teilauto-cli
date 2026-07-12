from __future__ import annotations

from click.testing import CliRunner

from teilauto import __version__
from teilauto.cli import cli


def test_version_flag():
    result = CliRunner().invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "teilauto" in result.output


def test_h_shows_help():
    result = CliRunner().invoke(cli, ["-h"])
    assert result.exit_code == 0
    assert "Manage teilauto/CityFlitzer" in result.output


def test_version_attribute():
    assert __version__
