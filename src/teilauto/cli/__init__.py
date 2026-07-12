from __future__ import annotations

import sys

import rich_click as click

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(package_name="teilauto-cli", prog_name="teilauto")
def cli() -> None:
    """Manage teilauto/CityFlitzer carsharing from your terminal."""


def main() -> None:
    try:
        cli(standalone_mode=False)
    except click.exceptions.Exit as exc:
        sys.exit(exc.exit_code)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
