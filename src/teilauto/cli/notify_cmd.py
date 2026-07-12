from __future__ import annotations

import rich_click as click

from teilauto.api.errors import ConfigError
from teilauto.output.render import console
from teilauto.services.notify import build_notifiers, send_all


@click.group()
def notify() -> None:
    """Notification channels (used by watch and autobook)."""


@notify.command("test")
@click.pass_obj
def test_notify(app) -> None:
    """Send a test message through every configured channel."""
    notifiers = build_notifiers(app.settings)
    if not notifiers:
        raise ConfigError(
            "No notification channels configured.",
            hint="Run `teilauto config set notify.channels telegram` (or ntfy) first.",
        )
    errors = send_all(notifiers, "teilauto test", "Test notification from teilauto ✓")
    failed = {e.split(":", 1)[0] for e in errors}
    for notifier in notifiers:
        if notifier.name in failed:
            console.print(f"[red]✗ {notifier.name} failed[/red]")
        else:
            console.print(f"[green]✓ {notifier.name} ok[/green]")
    if errors:
        raise ConfigError("; ".join(errors))
