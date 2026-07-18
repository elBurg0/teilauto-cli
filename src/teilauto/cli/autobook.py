from __future__ import annotations

import time
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

DEFAULT_DURATION = "1h"


@click.command("autobook")
@location_options
@click.option(
    "--for",
    "duration_text",
    default=None,
    metavar="DURATION",
    help=(
        f"Booking window sent to the API (default: {DEFAULT_DURATION}). CityFlitzer bills "
        "actual usage, so this only affects the availability check, not the price."
    ),
)
@click.option(
    "--until",
    "until_text",
    default=None,
    metavar="TIME",
    help="Fixed booking end time instead of --for.",
)
@click.option(
    "--min-fuel",
    type=float,
    default=None,
    metavar="PERCENT",
    help="Ignore cars below this fuel level (default: config).",
)
@click.option(
    "--deadline",
    "deadline_text",
    default=None,
    metavar="TIME",
    help="Give up (exit 2) if no car was booked by this time.",
)
@click.option(
    "--interval",
    type=int,
    default=None,
    metavar="SECONDS",
    help="Seconds between polls (default: config).",
)
@click.option(
    "--dry-run", is_flag=True, help="Do everything except the actual booking (no login needed)."
)
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@json_option
@click.pass_obj
def autobook_cmd(
    app,
    lat,
    lng,
    radius_m,
    duration_text,
    until_text,
    min_fuel,
    deadline_text,
    interval,
    dry_run,
    yes,
    as_json,
) -> None:
    """Book the closest CityFlitzer the moment one becomes available.

    This spends real money on your real account. Safety rails: a criteria
    confirmation before starting, --dry-run, and an optional --deadline.

    CityFlitzer billing follows actual usage (first hour in full, then
    15-minute steps, plus kilometers) — the booked window is a formality
    the API requires and is rewritten to the real end when you finish the
    trip. Exits as soon as a car is booked.
    """
    settings = app.settings
    lat, lng, radius_m = resolve_location(settings, lat, lng, radius_m)
    if duration_text and until_text:
        raise click.UsageError("--for and --until are mutually exclusive.")
    if not duration_text and not until_text:
        duration_text = DEFAULT_DURATION
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
                    "window": duration_text or f"until {until_text}",
                    "min fuel": f"{min_fuel:.0f}%",
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

    def finish(status: str, ca: CarAvailability | None, booking) -> None:
        if as_json:
            print_json(
                {
                    "status": status,
                    "car": ca.car if ca else None,
                    "booking": booking,
                }
            )

    with app.client() as client:

        def fetch():
            start, end = booking_window()
            return find_cars(
                client,
                lat=lat,
                lng=lng,
                radius_m=radius_m,
                start=start,
                end=end,
                min_fuel=min_fuel,
            )

        for error in send_all(
            notifiers,
            "teilauto autobook",
            f"🤖 Autobook started (radius {radius_m} m, every {interval}s)",
        ):
            err_console.print(f"[red]notify failed:[/red] {error}")
        if not app.quiet and not as_json:
            console.print(f"Hunting for a car... polling every {interval}s. Ctrl-C to stop.")

        def give_up(message: str) -> None:
            for error in send_all(notifiers, "Autobook gave up", f"⏰ {message}"):
                err_console.print(f"[red]notify failed:[/red] {error}")
            finish("no_match", None, None)
            raise NoMatchError(message)

        def deadline_passed() -> None:
            now = datetime.now().astimezone()
            if deadline is not None and now >= deadline:
                give_up("Deadline reached — no matching car was booked.")
            if fixed_end is not None and now >= fixed_end:
                give_up("The --until time has passed — nothing left to book.")

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
                    ca
                    for ca in tick.retryable
                    if failed_counts.get(ca.car.id, 0) > 0 and failed_counts.get(ca.car.id, 0) < 3
                ]
                for ca in list(tick.new) + retries:
                    start, end = booking_window()
                    if dry_run:
                        message = f"Would have booked: {describe(ca)}"
                        if not as_json:
                            console.print(f"[green]✓ DRY RUN[/green] {message}")
                        for error in send_all(notifiers, "teilauto dry-run", f"🤖 {message}"):
                            err_console.print(f"[red]notify failed:[/red] {error}")
                        finish("dry_run", ca, None)
                        return
                    try:
                        booking = client.create_booking(ca.car.id, start, end)
                    except AuthRequiredError:
                        raise
                    except TeilautoError as exc:
                        failed_counts[ca.car.id] = failed_counts.get(ca.car.id, 0) + 1
                        err_console.print(
                            f"  [yellow]booking failed (car taken?):[/yellow] {exc} — continuing"
                        )
                        if failed_counts[ca.car.id] >= 3:
                            err_console.print(
                                f"  [yellow]giving up on[/yellow] {describe(ca)} "
                                f"after 3 failed booking attempts"
                            )
                        continue
                    message = f"Booked {describe(ca)} — booking id {booking.id}"
                    if not as_json:
                        console.print(f"[green]✓ Booked![/green] {message}")
                    for error in send_all(notifiers, "Car booked", f"🚗 {message}"):
                        err_console.print(f"[red]notify failed:[/red] {error}")
                    finish("booked", ca, booking)
                    return
            deadline_passed()
