from __future__ import annotations

from datetime import datetime, timezone

import rich_click as click

from teilauto.api.errors import TeilautoError
from teilauto.api.models import Booking
from teilauto.cli.options import json_option, resolve_window, window_options
from teilauto.output.json_out import print_json
from teilauto.output.render import bookings_table, console, kv_panel, local_time


def _is_past(booking: Booking) -> bool:
    if not booking.end:
        return False
    try:
        end = datetime.fromisoformat(booking.end.replace("Z", "+00:00"))
    except ValueError:
        return False
    return end < datetime.now(timezone.utc)


@click.group()
def bookings() -> None:
    """List, create and cancel your bookings (login required)."""


@bookings.command("list")
@click.option("--all", "show_all", is_flag=True, help="Include past bookings.")
@json_option
@click.pass_obj
def list_bookings(app, show_all, as_json) -> None:
    """Show your bookings (upcoming only by default)."""
    with app.require_auth_client() as client:
        items = client.list_bookings()
    if not show_all:
        items = [b for b in items if not _is_past(b)]
    if as_json:
        print_json(items)
        return
    if not items:
        console.print("No bookings." if show_all else "No upcoming bookings (try --all).")
        return
    console.print(bookings_table(items))


@bookings.command("show")
@click.argument("booking_id")
@json_option
@click.pass_obj
def show_booking(app, booking_id, as_json) -> None:
    """Show one booking in detail."""
    with app.require_auth_client() as client:
        booking = client.get_booking(booking_id)
    if as_json:
        print_json(booking)
        return
    console.print(
        kv_panel(
            f"Booking {booking.id}",
            {
                "car": booking.bookee_id or "—",
                "from": local_time(booking.start),
                "until": local_time(booking.end),
                "state": booking.state or "—",
            },
        )
    )


@bookings.command("create")
@click.argument("car_id")
@window_options
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@json_option
@click.pass_obj
def create_booking(app, car_id, start_text, duration_text, until_text, yes, as_json) -> None:
    """Book CAR_ID for a time window. Asks for confirmation — this costs money."""
    start, end = resolve_window(
        start_text, duration_text, until_text, default_minutes=app.settings.window_min
    )
    with app.require_auth_client() as client:
        car = client.get_car(car_id)
        try:
            price = client.price(car_id, start, end)
            price_line = (
                f"{price.total:.2f} {price.currency}" if price.total is not None else "unknown"
            )
        except TeilautoError:
            price_line = "unknown"
        console.print(
            kv_panel(
                "Confirm booking",
                {
                    "car": f"{car.name} ({car.plate or car.id})",
                    "from": start.strftime("%Y-%m-%d %H:%M"),
                    "until": end.strftime("%Y-%m-%d %H:%M"),
                    "price": price_line,
                },
            )
        )
        if not yes:
            click.confirm("Book this car?", abort=True)
        booking = client.create_booking(car_id, start, end)
    if as_json:
        print_json(booking)
        return
    console.print(f"[green]✓ Booked.[/green] Booking id: {booking.id}")


@bookings.command("cancel")
@click.argument("booking_id")
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.pass_obj
def cancel_booking(app, booking_id, yes) -> None:
    """Cancel a booking."""
    if not yes:
        click.confirm(f"Cancel booking {booking_id}?", abort=True)
    with app.require_auth_client() as client:
        client.cancel_booking(booking_id)
    console.print(f"[green]✓ Booking {booking_id} cancelled.[/green]")
