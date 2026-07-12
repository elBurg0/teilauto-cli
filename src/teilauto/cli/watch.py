from __future__ import annotations

import time
from datetime import datetime, timedelta

import rich_click as click

from teilauto.cli.options import location_options, resolve_location
from teilauto.output.render import console, err_console
from teilauto.services.availability import describe, find_cars
from teilauto.services.notify import build_notifiers, send_all
from teilauto.services.watcher import watch


@click.command("watch")
@location_options
@click.option(
    "--min-fuel",
    type=float,
    default=None,
    metavar="PERCENT",
    help="Ignore cars below this fuel level (default: config).",
)
@click.option(
    "--window",
    "window_min",
    type=int,
    default=None,
    metavar="MINUTES",
    help="Booking window tested for availability (default: config).",
)
@click.option(
    "--interval",
    type=int,
    default=None,
    metavar="SECONDS",
    help="Seconds between polls (default: config).",
)
@click.pass_obj
def watch_cmd(app, lat, lng, radius_m, min_fuel, window_min, interval) -> None:
    """Watch for CityFlitzers becoming available and send a notification.

    Notify-only: nothing is ever booked. Use `teilauto autobook` to book
    automatically. Runs until interrupted with Ctrl-C.
    """
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    min_fuel = settings.min_fuel if min_fuel is None else min_fuel
    window_min = settings.window_min if window_min is None else window_min
    interval = settings.interval_sec if interval is None else interval

    notifiers = build_notifiers(settings)
    if not notifiers and not app.quiet:
        err_console.print(
            "[yellow]No notification channels configured — printing to terminal only.[/yellow]"
        )

    with app.client() as client:

        def fetch():
            start = datetime.now().astimezone()
            end = start + timedelta(minutes=window_min)
            return find_cars(
                client,
                lat=lat,
                lng=lng,
                radius_m=radius_m,
                start=start,
                end=end,
                min_fuel=min_fuel,
            )

        if not app.quiet:
            console.print(
                f"Watching CityFlitzers within {radius_m} m of ({lat}, {lng}); "
                f"polling every {interval}s. Ctrl-C to stop."
            )
        for error in send_all(
            notifiers,
            "teilauto watch",
            f"🚗 Watcher started (radius {radius_m} m, every {interval}s)",
        ):
            err_console.print(f"[red]notify failed:[/red] {error}")

        for tick in watch(fetch, interval=interval, sleeper=time.sleep):
            stamp = datetime.now().astimezone().strftime("%H:%M:%S")
            if tick.error:
                err_console.print(f"[dim]{stamp}[/dim] [red]poll failed:[/red] {tick.error}")
                continue
            extra = f", [green]{len(tick.new)} new[/green]" if tick.new else ""
            console.print(
                f"[dim]{stamp}[/dim] {tick.nearby} nearby, {tick.available} bookable{extra}"
            )
            for ca in tick.new:
                line = describe(ca)
                console.print(f"  [green]★[/green] {line}")
                for error in send_all(notifiers, "CityFlitzer available", f"🚗 {line}"):
                    err_console.print(f"[red]notify failed:[/red] {error}")
