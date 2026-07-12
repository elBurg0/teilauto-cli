from __future__ import annotations

import time
from contextlib import suppress
from datetime import datetime

import rich_click as click

from teilauto.api.errors import AuthRequiredError, NoMatchError, TeilautoError
from teilauto.cli.options import json_option, location_options, resolve_location
from teilauto.core.timeparse import parse_duration, parse_time
from teilauto.output.json_out import print_json
from teilauto.output.render import console, err_console, kv_panel
from teilauto.services.availability import CarAvailability, describe, find_cars
from teilauto.services.notify import build_notifiers, send_all
from teilauto.services.watcher import watch


@click.command("autobook")
@location_options
@click.option("--for", "duration_text", default=None, metavar="DURATION",
              help="Booking duration once a car is found, e.g. '45m', '2h'.")
@click.option("--until", "until_text", default=None, metavar="TIME",
              help="Fixed booking end time instead of --for.")
@click.option("--min-fuel", type=float, default=None, metavar="PERCENT",
              help="Ignore cars below this fuel level (default: config).")
@click.option("--max-price", type=float, default=None, metavar="EUR",
              help="Skip cars whose booking would cost more than this.")
@click.option("--deadline", "deadline_text", default=None, metavar="TIME",
              help="Give up (exit 2) if no car was booked by this time.")
@click.option("--interval", type=int, default=None, metavar="SECONDS",
              help="Seconds between polls (default: config).")
@click.option("--dry-run", is_flag=True,
              help="Do everything except the actual booking (no login needed).")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@json_option
@click.pass_obj
def autobook_cmd(app, lat, lng, radius_m, duration_text, until_text, min_fuel,
                 max_price, deadline_text, interval, dry_run, yes, as_json) -> None:
    """Book the closest matching CityFlitzer the moment one becomes available.

    This spends real money on your real account. Safety rails: a criteria
    confirmation before starting, --dry-run, --max-price, and an explicit
    booking duration. Exits as soon as a car is booked.
    """
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    if duration_text and until_text:
        raise click.UsageError("--for and --until are mutually exclusive.")
    if not duration_text and not until_text:
        raise click.UsageError("Give the booking length via --for (e.g. --for 1h) or --until.")
    try:
        duration = parse_duration(duration_text) if duration_text else None
        fixed_end = parse_time(until_text) if until_text else None
        deadline = parse_time(deadline_text) if deadline_text else None
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    min_fuel = settings.min_fuel if min_fuel is None else min_fuel
    interval = settings.interval_sec if interval is None else interval

    if as_json and not yes:
        raise click.UsageError("--json is non-interactive; add --yes to confirm the criteria.")

    if app.token is None and not dry_run:
        raise AuthRequiredError()

    notifiers = build_notifiers(settings)
    if not notifiers and not app.quiet and not as_json:
        err_console.print(
            "[yellow]No notification channels configured — printing to terminal only.[/yellow]"
        )

    if not yes:
        console.print(
            kv_panel(
                "Autobook criteria",
                {
                    "location": f"{lat}, {lng} (±{radius_m} m)",
                    "duration": duration_text or f"until {until_text}",
                    "min fuel": f"{min_fuel:.0f}%",
                    "max price": f"{max_price:.2f} EUR" if max_price is not None else "—",
                    "deadline": deadline_text or "—",
                    "mode": "DRY RUN" if dry_run else "books immediately",
                },
            )
        )
        click.confirm("Start autobook with these criteria?", abort=True)

    def booking_window() -> tuple[datetime, datetime]:
        start = datetime.now().astimezone()
        end = fixed_end if fixed_end is not None else start + duration
        return start, end

    def finish(status: str, ca: CarAvailability | None, booking, price) -> None:
        if as_json:
            print_json({"status": status, "car": ca.car if ca else None,
                        "booking": booking, "price": price})

    with app.client() as client:

        def fetch():
            start, end = booking_window()
            return find_cars(
                client, lat=lat, lng=lng, radius_m=radius_m,
                start=start, end=end, min_fuel=min_fuel,
            )

        send_all(notifiers, "teilauto autobook",
                 f"🤖 Autobook started (radius {radius_m} m, every {interval}s)")
        if not app.quiet and not as_json:
            console.print(f"Hunting for a car... polling every {interval}s. Ctrl-C to stop.")

        def give_up(message: str) -> None:
            send_all(notifiers, "Autobook gave up", f"⏰ {message}")
            finish("no_match", None, None, None)
            raise NoMatchError(message)

        def deadline_passed() -> bool:
            now = datetime.now().astimezone()
            if deadline is not None and now >= deadline:
                give_up("Deadline reached — no matching car was booked.")
            if fixed_end is not None and now >= fixed_end:
                give_up("The --until time has passed — nothing left to book.")
            return False

        deadline_passed()

        failed_counts: dict[str, int] = {}
        for tick in watch(fetch, interval=interval, sleeper=time.sleep):
            stamp = datetime.now().astimezone().strftime("%H:%M:%S")
            if tick.error:
                err_console.print(f"[dim]{stamp}[/dim] [red]poll failed:[/red] {tick.error}")
            else:
                if not app.quiet and not as_json:
                    console.print(
                        f"[dim]{stamp}[/dim] {tick.nearby} nearby, {tick.available} bookable"
                    )
                retries = [
                    ca for ca in tick.retryable
                    if failed_counts.get(ca.car.id, 0) > 0
                    and failed_counts.get(ca.car.id, 0) < 3
                ]
                for ca in list(tick.new) + retries:
                    start, end = booking_window()
                    price = None
                    with suppress(TeilautoError):
                        price = client.price(ca.car.id, start, end)
                    if max_price is not None and (price is None or price.total is None):
                        err_console.print(
                            f"  [yellow]skip[/yellow] {describe(ca)} "
                            f"(price unknown, --max-price set)"
                        )
                        continue
                    if (
                        max_price is not None
                        and price is not None
                        and price.total is not None
                        and price.total > max_price
                    ):
                        if not as_json:
                            console.print(
                                f"  [yellow]skip[/yellow] {describe(ca)} "
                                f"({price.total:.2f} {price.currency} > max)"
                            )
                        continue
                    price_line = (
                        f" for {price.total:.2f} {price.currency}"
                        if price and price.total is not None
                        else ""
                    )
                    if dry_run:
                        message = f"Would have booked: {describe(ca)}{price_line}"
                        if not as_json:
                            console.print(f"[green]✓ DRY RUN[/green] {message}")
                        send_all(notifiers, "teilauto dry-run", f"🤖 {message}")
                        finish("dry_run", ca, None, price)
                        return
                    try:
                        booking = client.create_booking(ca.car.id, start, end)
                    except AuthRequiredError:
                        raise
                    except TeilautoError as exc:
                        failed_counts[ca.car.id] = failed_counts.get(ca.car.id, 0) + 1
                        err_console.print(
                            f"  [yellow]booking failed (car taken?):[/yellow] {exc} — "
                            f"continuing"
                        )
                        if failed_counts[ca.car.id] >= 3:
                            err_console.print(
                                f"  [yellow]giving up on[/yellow] {describe(ca)} "
                                f"after 3 failed booking attempts"
                            )
                        continue
                    message = (
                        f"Booked {describe(ca)}{price_line} — booking id {booking.id}"
                    )
                    if not as_json:
                        console.print(f"[green]✓ Booked![/green] {message}")
                    send_all(notifiers, "Car booked", f"🚗 {message}")
                    finish("booked", ca, booking, price)
                    return
            deadline_passed()
