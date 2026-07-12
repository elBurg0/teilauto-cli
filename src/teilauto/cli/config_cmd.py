from __future__ import annotations

import rich_click as click
from rich.table import Table

from teilauto.api.errors import ConfigError
from teilauto.cli.options import json_option
from teilauto.core import config as cfg
from teilauto.core import tokenstore
from teilauto.output.json_out import print_json
from teilauto.output.render import console

SECRET_KEYS = {"notify.telegram.bot_token": tokenstore.TG_BOT_TOKEN_KEY}


def _check_key(key: str) -> None:
    if key not in cfg.KNOWN_KEYS and key not in SECRET_KEYS:
        valid = ", ".join((*cfg.KNOWN_KEYS, *SECRET_KEYS))
        raise ConfigError(f"Unknown config key: {key!r}.", hint=f"Valid keys: {valid}")


def _validate_value(key: str, value: object) -> object:
    """Check a coerced CLI value against the DEFAULTS leaf type, converting where safe."""
    default = cfg.get_value(cfg.DEFAULTS, key)
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise ConfigError(
                f"Invalid value for {key}: expected a boolean, got {value!r}.",
                hint=f"`teilauto config set {key} true|false`",
            )
        return value
    if isinstance(default, int):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(
                f"Invalid value for {key}: expected an integer, got {value!r}.",
                hint=f"`teilauto config set {key} <integer>`",
            )
        return value
    if isinstance(default, float):
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ConfigError(
                f"Invalid value for {key}: expected a number, got {value!r}.",
                hint=f"`teilauto config set {key} <number>`",
            )
        return value
    if isinstance(default, list):
        if not isinstance(value, (list, str)):
            raise ConfigError(
                f"Invalid value for {key}: expected a comma-separated list or a string, "
                f"got {value!r}.",
                hint=f"`teilauto config set {key} a,b,c`",
            )
        return value
    if isinstance(default, str):
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return str(value)
        raise ConfigError(
            f"Invalid value for {key}: expected a string, got {value!r}.",
            hint=f"`teilauto config set {key} <text>`",
        )
    return value


@click.group("config")
def config_group() -> None:
    """View and edit configuration (config file, overridable via TEILAUTO_* env vars)."""


@config_group.command("list")
@json_option
def list_config(as_json: bool) -> None:
    """Show the effective configuration (defaults + file + environment)."""
    flat = cfg.effective_config()
    if as_json:
        print_json(flat)
        return

    table = Table(title="Configuration", header_style="bold")
    table.add_column("Key")
    table.add_column("Value")
    for key, value in flat.items():
        table.add_row(key, repr(value))
    console.print(table)


@config_group.command("get")
@click.argument("key")
def get_config(key: str) -> None:
    """Print one effective config value (secrets show only whether they are set)."""
    _check_key(key)
    if key in SECRET_KEYS:
        value = tokenstore.load_secret(SECRET_KEYS[key])
        click.echo("(set)" if value else "(not set)")
        return
    click.echo(cfg.effective_config()[key])


@config_group.command("set")
@click.argument("key")
@click.argument("value")
def set_config(key: str, value: str) -> None:
    """Set a config value, e.g. `teilauto config set location.radius_m 800`.

    Secrets (notify.telegram.bot_token) are stored in the OS keyring, not the file.
    """
    _check_key(key)
    if key in SECRET_KEYS:
        tokenstore.save_secret(SECRET_KEYS[key], value)
        console.print(f"[green]✓[/green] {key} stored securely.")
        return
    coerced = _validate_value(key, cfg.coerce_value(value))
    data = cfg.read_raw()
    cfg.set_value(data, key, coerced)
    cfg.write_raw(data)
    console.print(f"[green]✓[/green] {key} = {coerced!r}")


@config_group.command("unset")
@click.argument("key")
def unset_config(key: str) -> None:
    """Remove a value from the config file (reverts to the default)."""
    _check_key(key)
    if key in SECRET_KEYS:
        tokenstore.delete_secret(SECRET_KEYS[key])
        console.print(f"[green]✓[/green] {key} removed.")
        return
    data = cfg.read_raw()
    cfg.unset_value(data, key)
    cfg.write_raw(data)
    console.print(f"[green]✓[/green] {key} removed.")


@config_group.command("path")
def config_path() -> None:
    """Print the config file location."""
    click.echo(cfg.config_file())
